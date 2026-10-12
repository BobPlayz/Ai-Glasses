import unittest
from unittest.mock import patch

from laptop.assistant.ollama_client import OllamaError, stream_local


class StreamLocalTests(unittest.TestCase):
    def test_empty_question_is_rejected(self):
        with self.assertRaises(OllamaError):
            list(stream_local("  "))

    def test_stream_yields_tokens_and_metadata(self):
        with patch("laptop.assistant.ollama_client._ollama_url", return_value="http://127.0.0.1:11434/api/chat"), patch(
            "laptop.assistant.ollama_client.urllib.request.urlopen"
        ) as open_url:
            class FakeResponse:
                def __enter__(self): return self
                def __exit__(self, *args): return False
                def __iter__(self):
                    return iter([
                        b'{"message":{"content":"Hello"},"done":false}\n',
                        b'{"message":{"content":" there."},"done":false}\n',
                        b'{"message":{"content":""},"done":true}\n',
                    ])
            open_url.return_value = FakeResponse()
            events = list(stream_local("test question", history=[]))
        self.assertEqual("".join(e["text"] for e in events if e["type"] == "token"), "Hello there.")
        self.assertEqual(events[-1]["type"], "meta")
        self.assertEqual(events[-1]["model"], "qwen2.5:1.5b")


if __name__ == "__main__":
    unittest.main()
