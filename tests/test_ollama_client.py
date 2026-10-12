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

    def test_gen_z_prompt_is_natural_and_uses_real_newlines(self):
        response = {"message": {"content": "Sounds normal."}}

        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return json.dumps(response).encode()

        captured = {}
        def fake_urlopen(request, timeout=None):
            captured["payload"] = json.loads(request.data.decode())
            return FakeResponse()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with patch.dict("os.environ", {"GLASSES_MODEL": "test-primary", "GLASSES_FALLBACK_MODEL": ""}):
                ask_local("yo", gen_z_mode=True)

        system_prompt = captured["payload"]["messages"][0]["content"]
        self.assertIn("\n\nSTYLE MODE: Natural casual conversation", system_prompt)
        self.assertNotIn("\\n\\nSTYLE MODE: Natural casual conversation", system_prompt)
        self.assertIn("Never mechanically sprinkle in 'bro'", system_prompt)


if __name__ == "__main__":
    unittest.main()
