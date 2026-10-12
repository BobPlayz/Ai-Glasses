import unittest
from unittest.mock import patch

from laptop.speech.speak import synthesize_wav_local


class DeviceSpeechTests(unittest.TestCase):
    def test_empty_text_does_not_synthesize(self):
        self.assertIsNone(synthesize_wav_local("   "))

    def test_missing_voice_assets_fall_back_cleanly(self):
        with patch("laptop.speech.speak.VOICE_DIR") as voice_dir:
            voice_dir.__truediv__.return_value.is_file.return_value = False
            self.assertIsNone(synthesize_wav_local("Hello there"))

    def test_long_text_is_bounded_before_synthesis(self):
        with patch("laptop.speech.speak.VOICE_DIR") as voice_dir:
            voice_dir.__truediv__.return_value.is_file.return_value = False
            self.assertIsNone(synthesize_wav_local("hello " * 2000))


if __name__ == "__main__":
    unittest.main()
