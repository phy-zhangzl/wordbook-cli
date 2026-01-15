import unittest
from datetime import datetime, timezone

from word_agent.models import WordbookEntry
from word_agent.review import apply_review_score, ensure_review_defaults, is_due, parse_iso_datetime


class TestReview(unittest.TestCase):
    def test_review_defaults_and_due(self):
        now = datetime(2024, 1, 1, tzinfo=timezone.utc)
        entry = WordbookEntry(
            word="hello",
            lemma="hello",
            pos="interj",
            pronunciation="heh-low",
        )
        self.assertTrue(is_due(entry, now))
        ensure_review_defaults(entry, now)
        self.assertEqual(entry.review_due, now.isoformat())

    def test_apply_review_score_advances_due(self):
        now = datetime(2024, 1, 1, tzinfo=timezone.utc)
        entry = WordbookEntry(
            word="hello",
            lemma="hello",
            pos="interj",
            pronunciation="heh-low",
            review_due=now.isoformat(),
            review_interval_days=1.0,
            review_ease=2.5,
        )
        apply_review_score(entry, 5, now)
        due = parse_iso_datetime(entry.review_due)
        self.assertIsNotNone(due)
        self.assertGreater(due, now)


if __name__ == "__main__":
    unittest.main()
