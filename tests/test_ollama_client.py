import json
import unittest
from unittest.mock import patch

from laptop.assistant.ollama_client import OllamaError, _ollama_url, ask_local


class OllamaClientTests(unittest.TestCase):
    def test_rejects_remote_host(self):
        with patch.dict("os.environ", {"OLLAMA_HOST": "https://example.com"}):
            with self.assertRaises(OllamaError):
                _ollama_url("/api/tags")

    def test_primary_model_reply(self):
        response = {
            "message": {"content": "Hello from local model"},
        }
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps(response).encode()

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            with patch.dict("os.environ", {
                "GLASSES_MODEL": "test-primary",
                "GLASSES_FALLBACK_MODEL": "test-fallback",
            }):
                result = ask_local("Hello")
        self.assertEqual(result.text, "Hello from local model")
        self.assertEqual(result.model, "test-primary")
        self.assertFalse(result.used_fallback)

    def test_empty_question_is_rejected(self):
        with self.assertRaises(OllamaError):
            ask_local("   ")


if __name__ == "__main__":
    unittest.main()
