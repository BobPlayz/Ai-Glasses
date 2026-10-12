import json
import tempfile
import unittest
from collections import deque
from pathlib import Path
from unittest.mock import patch

from laptop.speech import speak


class OnlineVoiceDefaultTests(unittest.TestCase):
    def test_online_voice_is_enabled_when_no_preference_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "voice-mode.json"
            with patch.object(speak, "ONLINE_VOICE_MODE_PATH", path):
                self.assertTrue(speak.online_voice_enabled())

    def test_saved_offline_preference_is_respected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "voice-mode.json"
            path.write_text(json.dumps({"enabled": False}), encoding="utf-8")
            with patch.object(speak, "ONLINE_VOICE_MODE_PATH", path):
                self.assertFalse(speak.online_voice_enabled())

    def test_saved_online_preference_is_respected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "voice-mode.json"
            path.write_text(json.dumps({"enabled": True}), encoding="utf-8")
            with patch.object(speak, "ONLINE_VOICE_MODE_PATH", path):
                self.assertTrue(speak.online_voice_enabled())

    def test_invalid_saved_preference_fails_closed_to_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "voice-mode.json"
            path.write_text("{broken", encoding="utf-8")
            with patch.object(speak, "ONLINE_VOICE_MODE_PATH", path):
                self.assertFalse(speak.online_voice_enabled())


class DeviceSpeechQueueTests(unittest.TestCase):
    def test_pending_queue_does_not_reference_missing_global(self):
        from laptop import app as app_module
        queue = deque([(b"RIFFtest", 100.0)])
        with patch.object(app_module, "_speech_queue", queue), patch("laptop.app.time.time", return_value=105.0):
            self.assertTrue(app_module.has_pending_device_speech())

    def test_expired_audio_is_pruned(self):
        from laptop import app as app_module
        queue = deque([(b"old", 10.0), (b"new", 95.0)])
        with patch.object(app_module, "_speech_queue", queue), patch("laptop.app.time.time", return_value=100.0):
            self.assertTrue(app_module.has_pending_device_speech())
            self.assertEqual(len(queue), 1)
            self.assertEqual(queue[0][0], b"new")

    def test_all_expired_audio_is_not_reported_pending(self):
        from laptop import app as app_module
        queue = deque([(b"old", 10.0)])
        with patch.object(app_module, "_speech_queue", queue), patch("laptop.app.time.time", return_value=100.0):
            self.assertFalse(app_module.has_pending_device_speech())
            self.assertFalse(queue)



class VoiceModeApiTests(unittest.TestCase):
    def test_voice_mode_api_reads_default_and_persists_user_choice(self):
        from fastapi.testclient import TestClient
        from laptop import app as app_module

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "voice-mode.json"
            with patch.object(app_module, "VOICE_MODE_PATH", path), patch.object(speak, "ONLINE_VOICE_MODE_PATH", path), patch.dict("os.environ", {"GLASSES_LAN_MODE": "0"}):
                client = TestClient(app_module.app)
                initial = client.get("/api/voice-mode")
                self.assertEqual(initial.status_code, 200)
                self.assertTrue(initial.json()["online_voice"])

                saved = client.post("/api/voice-mode", json={"enabled": False})
                self.assertEqual(saved.status_code, 200)
                self.assertFalse(saved.json()["online_voice"])
                self.assertFalse(speak.online_voice_enabled())
                self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"enabled": False})

if __name__ == "__main__":
    unittest.main()
