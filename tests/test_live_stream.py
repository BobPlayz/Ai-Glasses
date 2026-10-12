import unittest

from laptop.vision.live_stream import _validate_lan_stream_url
from laptop.vision.local_vision import VisionError


class LiveStreamUrlTests(unittest.TestCase):
    def test_accepts_private_lan_stream_with_port(self):
        _validate_lan_stream_url("http://192.168.1.40:8080/video")

    def test_accepts_loopback_stream_with_port(self):
        _validate_lan_stream_url("http://127.0.0.1:8080/video")

    def test_rejects_public_ip(self):
        with self.assertRaises(VisionError):
            _validate_lan_stream_url("http://8.8.8.8:8080/video")

    def test_rejects_hostname(self):
        with self.assertRaises(VisionError):
            _validate_lan_stream_url("http://camera.local:8080/video")

    def test_rejects_embedded_credentials(self):
        with self.assertRaises(VisionError):
            _validate_lan_stream_url("http://user:pass@192.168.1.40:8080/video")

    def test_requires_explicit_port(self):
        with self.assertRaises(VisionError):
            _validate_lan_stream_url("http://192.168.1.40/video")


if __name__ == "__main__":
    unittest.main()
