import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        self.old_voice_armed = glasses_app._voice_armed
        self.old_voice_parts = glasses_app._voice_question_parts
        self.old_capture_request = glasses_app._capture_request
        self.old_last_frame = glasses_app._last_frame
        self.addCleanup(self.restore_state)

        glasses_app.DEVICE_TOKEN_PATH = root / ".device-token"
        glasses_app.DEVICE_TOKEN_PATH.write_text("test-device-token", encoding="utf-8")
        glasses_app.PIN_PATH = root / ".dashboard-pin"
        os.environ["GLASSES_LAN_MODE"] = "0"
        glasses_app._dashboard_microphone_enabled = False
        glasses_app._dashboard_camera_enabled = False
        glasses_app._last_device_status = {"connected": False}
        glasses_app._voice_last_event = {"state": "idle", "detail": ""}
        glasses_app._voice_armed = False
        glasses_app._voice_question_parts = []
        glasses_app._capture_request = None
        glasses_app._last_frame = None
        self.client = TestClient(glasses_app.app)
        self.headers = {"X-Device-Token": "test-device-token"}

    def restore_state(self):
        glasses_app.DEVICE_TOKEN_PATH = self.old_token_path
        glasses_app.PIN_PATH = self.old_pin_path
        glasses_app._dashboard_microphone_enabled = self.old_mic_enabled
        glasses_app._dashboard_camera_enabled = self.old_camera_enabled
        glasses_app._last_device_status = self.old_status
        glasses_app._voice_last_event = self.old_voice_state
        glasses_app._voice_armed = self.old_voice_armed
        glasses_app._voice_question_parts = self.old_voice_parts
        glasses_app._capture_request = self.old_capture_request
        glasses_app._last_frame = self.old_last_frame
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

    def test_large_device_audio_chunk_is_rejected_before_transcription(self):
        glasses_app._dashboard_microphone_enabled = True
        oversized = b"RIFF" + b"\x00" * (2 * 1024 * 1024 - 3) + b"WAVE"
        with patch("laptop.app.transcribe_audio_file") as transcribe:
            response = self.client.post(
                "/api/device/audio",
                headers={**self.headers, "Content-Type": "audio/wav"},
                content=oversized,
            )
        self.assertEqual(response.status_code, 413)
        transcribe.assert_not_called()

    def test_responses_include_baseline_security_headers(self):
        response = self.client.get("/api/status")
        self.assertEqual(response.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(response.headers.get("x-frame-options"), "DENY")
        self.assertEqual(response.headers.get("referrer-policy"), "no-referrer")
        self.assertEqual(response.headers.get("cache-control"), "no-store")

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

    def test_enabled_microphone_audio_reaches_local_transcriber(self):
        self.client.post("/api/microphone/control", json={"enabled": True})
        with patch("laptop.app.transcribe_audio_file", return_value={"text": "", "model": "base"}):
            response = self.client.post(
                "/api/device/audio",
                headers={**self.headers, "Content-Type": "audio/wav"},
                content=b"RIFF\x00\x00\x00\x00WAVE",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "listening")

    def test_lan_dashboard_mutation_requires_pin(self):
        os.environ["GLASSES_LAN_MODE"] = "1"
        glasses_app.PIN_PATH.write_text("test-pin", encoding="utf-8")
        missing_pin = self.client.post("/api/microphone/control", json={"enabled": True})
        self.assertEqual(missing_pin.status_code, 401)
        valid_pin = self.client.post(
            "/api/microphone/control",
            headers={"X-Dashboard-Pin": "test-pin"},
            json={"enabled": True},
        )
        self.assertEqual(valid_pin.status_code, 200)

    def test_phone_camera_rejects_public_ip(self):
        response = self.client.post(
            "/api/phone-camera/analyze",
            json={"snapshot_url": "http://8.8.8.8:8080/shot.jpg", "question": "What is this?"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("private", response.json()["detail"].lower())

    def test_phone_camera_requires_snapshot_image_path(self):
        response = self.client.post(
            "/api/phone-camera/analyze",
            json={"snapshot_url": "http://192.168.1.50:8080/video", "question": "What is this?"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("shot.jpg", response.json()["detail"])

    def test_device_routes_require_pairing_token(self):
        response = self.client.get("/api/device/command")
        self.assertEqual(response.status_code, 401)

    def test_camera_control_starts_disabled_and_can_be_revoked(self):
        self.assertFalse(glasses_app._dashboard_camera_enabled)
        enabled = self.client.post("/api/camera/control", json={"enabled": True})
        self.assertTrue(enabled.json()["dashboard_camera_enabled"])
        disabled = self.client.post("/api/camera/control", json={"enabled": False})
        self.assertFalse(disabled.json()["dashboard_camera_enabled"])


    def _prepare_capture_upload(self, *, status_age=0, camera_enabled=True, privacy=True, indicator=True):
        glasses_app._dashboard_camera_enabled = True
        glasses_app._capture_request = {
            "id": "capture-test",
            "question": "What is this?",
            "expires_at": glasses_app.time.time() + 10,
        }
        glasses_app._last_device_status = {
            "connected": True,
            "camera_enabled": camera_enabled,
            "privacy_switch_enabled": privacy,
            "indicator_on": indicator,
            "updated_at": glasses_app.time.time() - status_age,
        }

    def test_camera_upload_requires_fresh_status_and_all_privacy_signals(self):
        self._prepare_capture_upload(status_age=13)
        response = self.client.post(
            "/api/device/capture-result?request_id=capture-test",
            headers=self.headers,
            files={"file": ("frame.jpg", bytes.fromhex("ffd8ffd9"), "image/jpeg")},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Fresh device status", response.json()["detail"])

    def test_camera_upload_rejects_frame_without_jpeg_signature(self):
        self._prepare_capture_upload()
        response = self.client.post(
            "/api/device/capture-result?request_id=capture-test",
            headers=self.headers,
            files={"file": ("frame.jpg", b"not a jpeg", "image/jpeg")},
        )
        self.assertEqual(response.status_code, 415)

    def test_camera_upload_requires_dashboard_permission(self):
        self._prepare_capture_upload()
        glasses_app._dashboard_camera_enabled = False
        response = self.client.post(
            "/api/device/capture-result?request_id=capture-test",
            headers=self.headers,
            files={"file": ("frame.jpg", bytes.fromhex("ffd8ffd9"), "image/jpeg")},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Dashboard camera permission", response.json()["detail"])

    def test_valid_camera_upload_requires_and_accepts_all_privacy_signals(self):
        self._prepare_capture_upload()
        response = self.client.post(
            "/api/device/capture-result?request_id=capture-test",
            headers=self.headers,
            files={"file": ("frame.jpg", bytes.fromhex("ffd8ffd9"), "image/jpeg")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["accepted"])
        self.assertEqual(glasses_app._last_frame["request_id"], "capture-test")


if __name__ == "__main__":
    unittest.main()
