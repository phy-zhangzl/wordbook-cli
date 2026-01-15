import tempfile
import unittest
from pathlib import Path

from word_agent.models import WordbookEntry
from word_agent.wordbook import Wordbook


class TestWordbook(unittest.TestCase):
    def test_upsert_and_find(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "wordbook.csv"
            wordbook = Wordbook(path)
            entry = WordbookEntry(
                word="hello",
                lemma="hello",
                pos="interj",
                pronunciation="heh-low",
                definitions_en=["greeting"],
                translations_zh=["ni hao"],
                examples=["hello there"],
                word_forms=["plural: hellos"],
                usage_tips=["Use as a greeting in informal settings."],
                mnemonics=["Sounds like 'hello' to remember it."],
                source="local:ecdict.csv",
                model="",
                confidence=0.9,
                review_due="2024-01-01T00:00:00+00:00",
                review_interval_days=1.0,
                review_ease=2.5,
                review_streak=1,
                review_lapses=0,
                reviewed_at="2024-01-01T00:00:00+00:00",
                review_tip="Remember: say it aloud like greeting a friend.",
                confusions=["hallo", "hullo"],
            )
            wordbook.upsert(entry)
            loaded = wordbook.find("hello")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.word, "hello")
            self.assertIn("greeting", loaded.definitions_en)
            self.assertIn("plural: hellos", loaded.word_forms)
            self.assertIn("Use as a greeting in informal settings.", loaded.usage_tips)
            self.assertIn("Sounds like 'hello' to remember it.", loaded.mnemonics)
            self.assertEqual(loaded.review_due, "2024-01-01T00:00:00+00:00")
            self.assertEqual(loaded.review_interval_days, 1.0)
            self.assertEqual(loaded.review_ease, 2.5)
            self.assertEqual(loaded.review_streak, 1)
            self.assertEqual(loaded.review_lapses, 0)
            self.assertEqual(loaded.reviewed_at, "2024-01-01T00:00:00+00:00")
            self.assertEqual(loaded.review_tip, "Remember: say it aloud like greeting a friend.")
            self.assertIn("hallo", loaded.confusions)


if __name__ == "__main__":
    unittest.main()
