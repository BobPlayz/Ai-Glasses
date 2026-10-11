import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from laptop import app as glasses_app


class DevicePrivacyApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.old_token_path = glasses_app.DEVICE_TOKEN_PATH
        self.old_pin_path = glasses_app.PIN_PATH
        self.old_lan_mode = os.environ.get("GLASSES_LAN_MODE")
        self.old_mic_enabled = glasses_app._dashboard_microphone_enabled
        self.old_camera_enabled = glasses_app._dashboard_camera_enabled
        self.old_status = glasses_app._last_device_status
        self.old_voice_state = glasses_app._voice_last_event
        self.addCleanup(self.restore_state)

        glasses_app.DEVICE_TOKEN_PATH = root / ".device-token"
        glasses_app.DEVICE_TOKEN_PATH.write_text("test-device-token", encoding="utf-8")
        glasses_app.PIN_PATH = root / ".dashboard-pin"
        os.environ["GLASSES_LAN_MODE"] = "0"
        glasses_app._dashboard_microphone_enabled = False
        glasses_app._dashboard_camera_enabled = False
        glasses_app._last_device_status = {"connected": False}
        glasses_app._voice_last_event = {"state": "idle", "detail": ""}
        self.client = TestClient(glasses_app.app)
        self.headers = {"X-Device-Token": "test-device-token"}

    def restore_state(self):
        glasses_app.DEVICE_TOKEN_PATH = self.old_token_path
        glasses_app.PIN_PATH = self.old_pin_path
        glasses_app._dashboard_microphone_enabled = self.old_mic_enabled
        glasses_app._dashboard_camera_enabled = self.old_camera_enabled
        glasses_app._last_device_status = self.old_status
        glasses_app._voice_last_event = self.old_voice_state
        if self.old_lan_mode is None:
            os.environ.pop("GLASSES_LAN_MODE", None)
        else:
            os.environ["GLASSES_LAN_MODE"] = self.old_lan_mode

    def test_device_command_denies_camera_and_microphone_by_default(self):
        response = self.client.get("/api/device/command", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["camera_allowed"])
        self.assertFalse(response.json()["microphone_allowed"])
        self.assertIsNone(response.json()["capture"])

    def test_device_audio_is_rejected_until_microphone_opt_in(self):
        response = self.client.post(
            "/api/device/audio",
            headers={**self.headers, "Content-Type": "audio/wav"},
            content=b"RIFF\x00\x00\x00\x00WAVE",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("disabled", response.json()["detail"].lower())

    def test_dashboard_can_explicitly_enable_and_disable_microphone(self):
        enabled = self.client.post("/api/microphone/control", json={"enabled": True})
        self.assertEqual(enabled.status_code, 200)
        self.assertTrue(enabled.json()["dashboard_microphone_enabled"])
        command = self.client.get("/api/device/command", headers=self.headers)
        self.assertTrue(command.json()["microphone_allowed"])

        disabled = self.client.post("/api/microphone/control", json={"enabled": False})
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.json()["dashboard_microphone_enabled"])
        command = self.client.get("/api/device/command", headers=self.headers)
        self.assertFalse(command.json()["microphone_allowed"])

    def test_device_routes_require_pairing_token(self):
        response = self.client.get("/api/device/command")
        self.assertEqual(response.status_code, 401)

    def test_camera_control_starts_disabled_and_can_be_revoked(self):
        self.assertFalse(glasses_app._dashboard_camera_enabled)
        enabled = self.client.post("/api/camera/control", json={"enabled": True})
        self.assertTrue(enabled.json()["dashboard_camera_enabled"])
        disabled = self.client.post("/api/camera/control", json={"enabled": False})
        self.assertFalse(disabled.json()["dashboard_camera_enabled"])


if __name__ == "__main__":
    unittest.main()
