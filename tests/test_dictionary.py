import tempfile
import unittest
from pathlib import Path

from word_agent.dictionary import EcdictDictionary


class TestEcdictDictionary(unittest.TestCase):
    def setUp(self):
        self.fixture = Path(__file__).parent / "fixtures" / "ecdict_sample.csv"
        self.dictionary = EcdictDictionary(self.fixture)

    def test_lookup(self):
        entry = self.dictionary.lookup("hello")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.word, "hello")
        self.assertIn("greeting", " ".join(entry.definitions_en))
        self.assertIn("ni hao", " ".join(entry.translations_zh))
        self.assertEqual(entry.pronunciation, "heh-low")

    def test_suggest(self):
        suggestions = self.dictionary.suggest("wor")
        self.assertIn("world", suggestions)

    def test_cache_written(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            fixture_copy = temp_path / "ecdict_sample.csv"
            fixture_copy.write_text(self.fixture.read_text(encoding="utf-8"), encoding="utf-8")
            cache_dir = temp_path / "cache"
            dictionary = EcdictDictionary(fixture_copy, cache_dir=cache_dir)
            entry = dictionary.lookup("hello")
            self.assertIsNotNone(entry)
            cache_files = list(cache_dir.glob("*.sqlite"))
            self.assertEqual(len(cache_files), 1)


if __name__ == "__main__":
    unittest.main()
