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


class NoRedirectCameraFetchTests(unittest.TestCase):
    def test_private_camera_redirect_is_not_followed(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from urllib.error import HTTPError
        from urllib.request import Request

        from laptop.vision.lan_http import open_no_redirect

        class RedirectHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", "http://8.8.8.8:8080/redirect-target")
                self.end_headers()

            def log_message(self, format, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        request = Request(f"http://127.0.0.1:{server.server_port}/camera.jpg")
        with self.assertRaises(HTTPError) as raised:
            open_no_redirect(request, timeout=2)
        self.assertEqual(raised.exception.code, 302)


if __name__ == "__main__":
    unittest.main()
