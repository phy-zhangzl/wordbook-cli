import json
import unittest
from unittest.mock import patch

from word_agent.models import DictionaryEntry
from word_agent.providers import OllamaProvider, get_provider


class FakeResponse:
    def __init__(self, body: dict):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.body).encode("utf-8")


class TestProviders(unittest.TestCase):
    def test_get_provider_supports_ollama_without_api_key(self):
        provider = get_provider(
            provider="ollama",
            api_base="http://localhost:11434",
            api_key="",
            model="test-model",
        )
        self.assertIsInstance(provider, OllamaProvider)

    def test_ollama_enhance_parses_json_response(self):
        body = {
            "message": {
                "content": json.dumps(
                    {
                        "definitions_en": ["Adapting a pretrained model to a task."],
                        "translations_zh": ["微调"],
                        "examples": ["Fine-tuning improves accuracy."],
                        "word_forms": [],
                        "usage_tips": [],
                        "mnemonics": [],
                        "pronunciation": "",
                    }
                )
            }
        }
        provider = OllamaProvider("http://localhost:11434", "test-model")
        entry = DictionaryEntry(
            word="fine-tuning",
            lemma="fine-tuning",
            pos="term",
            pronunciation="",
            definitions_en=[],
            translations_zh=[],
        )
        with patch("urllib.request.urlopen", return_value=FakeResponse(body)) as mocked:
            enhancement = provider.enhance(entry)
        self.assertEqual(enhancement.translations_zh, ["微调"])
        request = mocked.call_args.args[0]
        self.assertEqual(request.full_url, "http://localhost:11434/api/chat")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "test-model")
        self.assertFalse(payload["stream"])


if __name__ == "__main__":
    unittest.main()
