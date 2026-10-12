import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from PIL import Image

from laptop.vision.local_vision import VisionError, ask_image_local


def png_bytes():
    image = Image.new("RGB", (32, 24), "white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


def response(answer):
    return FakeResponse(json.dumps({"message": {"content": answer}}).encode("utf-8"))


def http_error(status=500, body=b'{"error":"model unavailable"}'):
    return urllib.error.HTTPError(
        "http://127.0.0.1:11434/api/chat", status, "test error", {}, io.BytesIO(body)
    )


class LocalVisionTests(unittest.TestCase):
    def setUp(self):
        self.ocr_patch = patch("laptop.vision.local_vision.extract_text_local", return_value="")
        self.ocr_patch.start()
        self.addCleanup(self.ocr_patch.stop)

    def test_generated_png_succeeds_through_application_vision_function(self):
        with patch("laptop.vision.local_vision.urllib.request.urlopen", return_value=response("A white image.")) as request:
            result = ask_image_local(png_bytes(), "Describe this image.")
        self.assertEqual(result["answer"], "A white image.")
        self.assertTrue(result["offline"])
        self.assertEqual(request.call_count, 1)

    def test_empty_first_answer_retries_and_succeeds(self):
        with patch(
            "laptop.vision.local_vision.urllib.request.urlopen",
            side_effect=[response(""), response("A red apple.")],
        ) as request:
            result = ask_image_local(png_bytes(), "What is this?")
        self.assertEqual(result["answer"], "A red apple.")
        self.assertEqual(request.call_count, 2)

    def test_empty_answers_twice_return_actionable_error(self):
        with patch(
            "laptop.vision.local_vision.urllib.request.urlopen",
            side_effect=[response(""), response("")],
        ):
            with self.assertRaisesRegex(VisionError, "either attempt"):
                ask_image_local(png_bytes(), "What is this?")

    def test_first_attempt_http_error_preserves_status_and_body(self):
        with patch(
            "laptop.vision.local_vision.urllib.request.urlopen",
            side_effect=http_error(404, b'{"error":"model not found"}'),
        ):
            with self.assertRaisesRegex(VisionError, "HTTP 404.*model not found"):
                ask_image_local(png_bytes(), "What is this?")

    def test_retry_http_error_preserves_status_and_body(self):
        with patch(
            "laptop.vision.local_vision.urllib.request.urlopen",
            side_effect=[response(""), http_error(500, b'{"error":"model crashed"}')],
        ):
            with self.assertRaisesRegex(VisionError, "attempt 2 failed with HTTP 500.*model crashed"):
                ask_image_local(png_bytes(), "What is this?")

    def test_first_attempt_timeout_is_actionable(self):
        with patch(
            "laptop.vision.local_vision.urllib.request.urlopen",
            side_effect=TimeoutError("simulated timeout"),
        ):
            with self.assertRaisesRegex(VisionError, "TimeoutError.*simulated timeout"):
                ask_image_local(png_bytes(), "What is this?")

    def test_retry_timeout_is_actionable(self):
        with patch(
            "laptop.vision.local_vision.urllib.request.urlopen",
            side_effect=[response(""), TimeoutError("retry timed out")],
        ):
            with self.assertRaisesRegex(VisionError, "attempt 2 failed.*retry timed out"):
                ask_image_local(png_bytes(), "What is this?")

    def test_invalid_json_is_reported(self):
        with patch(
            "laptop.vision.local_vision.urllib.request.urlopen",
            return_value=FakeResponse(b"not json"),
        ):
            with self.assertRaisesRegex(VisionError, "attempt 1 returned invalid JSON"):
                ask_image_local(png_bytes(), "What is this?")

    def test_public_ollama_host_is_rejected_before_request(self):
        with patch.dict("os.environ", {"OLLAMA_HOST": "http://8.8.8.8:11434"}):
            with patch("laptop.vision.local_vision.urllib.request.urlopen") as request:
                with self.assertRaisesRegex(VisionError, "restricted to the local Ollama"):
                    ask_image_local(png_bytes(), "What is this?")
                request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
