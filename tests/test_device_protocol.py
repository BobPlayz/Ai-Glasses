import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from laptop.app import app, DEVICE_TOKEN_PATH, PIN_PATH, WAKE_PHRASE_PATH, normalize_speech, is_visual_question


class DeviceProtocolTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.old_token = DEVICE_TOKEN_PATH.read_text() if DEVICE_TOKEN_PATH.exists() else None
        self.old_pin = PIN_PATH.read_text() if PIN_PATH.exists() else None
        self.old_wake_phrase = WAKE_PHRASE_PATH.read_text() if WAKE_PHRASE_PATH.exists() else None
        app_module = __import__("laptop.app", fromlist=["_dashboard_camera_enabled"])
        app_module._dashboard_camera_enabled = False
        app_module._voice_armed = False
        app_module._voice_question_parts = []
        DEVICE_TOKEN_PATH.write_text("test-device-token")
        PIN_PATH.write_text("test-dashboard-pin")

    def tearDown(self):
        if self.old_token is None:
            DEVICE_TOKEN_PATH.unlink(missing_ok=True)
        else:
            DEVICE_TOKEN_PATH.write_text(self.old_token)
        if self.old_pin is None:
            PIN_PATH.unlink(missing_ok=True)
        else:
            PIN_PATH.write_text(self.old_pin)
        if self.old_wake_phrase is None:
            WAKE_PHRASE_PATH.unlink(missing_ok=True)
        else:
            WAKE_PHRASE_PATH.write_text(self.old_wake_phrase)

    def test_unicode_wake_phrase_normalization(self):
        self.assertEqual(normalize_speech("Hey, glasses!"), "hey glasses")
        self.assertEqual(normalize_speech("హే గ్లాసెస్"), "హే గ్లాసెస్")

    def test_visual_question_detection_in_english_and_telugu(self):
        self.assertTrue(is_visual_question("What am I looking at?"))
        self.assertTrue(is_visual_question("Read this sign"))
        self.assertTrue(is_visual_question("ఇది ఏమిటి"))
        self.assertFalse(is_visual_question("What is the capital of India?"))

    def test_wake_phrase_detection_is_local(self):
        from unittest.mock import patch
        WAKE_PHRASE_PATH.write_text("hey glasses")
        wav = b"RIFF" + b"0000" + b"WAVE" + b"test-audio"
        with patch("laptop.app.transcribe_audio_file", return_value={"text": "Hey, glasses", "language": "en"}):
            response = self.client.post(
                "/api/device/audio",
                content=wav,
                headers={"X-Device-Token": "test-device-token", "Content-Type": "audio/wav"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["wake_detected"])
        self.assertEqual(response.json()["state"], "awake")

    def test_camera_capture_disabled_by_default(self):
        with patch.dict("os.environ", {"GLASSES_LAN_MODE":"0"}):
            response = self.client.post("/api/device/capture", json={"question":"What am I looking at?"})
        self.assertEqual(response.status_code, 403)

    def test_device_token_required(self):
        response = self.client.get("/api/device/command")
        self.assertEqual(response.status_code, 401)

    def test_device_command_with_token(self):
        response = self.client.get("/api/device/command", headers={"X-Device-Token":"test-device-token"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("capture", response.json())

    def test_lan_dashboard_pin_required(self):
        with patch.dict("os.environ", {"GLASSES_LAN_MODE":"1"}):
            response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 401)

    def test_localhost_mode_does_not_require_pin(self):
        with patch.dict("os.environ", {"GLASSES_LAN_MODE":"0"}):
            response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
