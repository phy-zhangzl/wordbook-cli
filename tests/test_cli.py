import io
import tempfile
import unittest
from pathlib import Path

from word_agent import cli
from word_agent.models import ModelEnhancement, WordbookEntry
from word_agent.wordbook import Wordbook


class FakeInput(io.StringIO):
    def isatty(self):
        return True


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.fixture = Path(__file__).parent / "fixtures" / "ecdict_sample.csv"

    def test_cli_saves_on_prompt_yes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            wordbook_path = Path(temp_dir) / "wordbook.csv"
            args = [
                "hello",
                "--dict",
                str(self.fixture),
                "--wordbook",
                str(wordbook_path),
                "--no-remote",
            ]
            input_stream = FakeInput("y\n")
            output_stream = io.StringIO()
            exit_code = cli.main(args, input_stream=input_stream, output_stream=output_stream)
            self.assertEqual(exit_code, 0)
            wordbook = Wordbook(wordbook_path)
            entry = wordbook.find("hello")
            self.assertIsNotNone(entry)

    def test_cli_handles_missing_word(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            wordbook_path = Path(temp_dir) / "wordbook.csv"
            args = [
                "unknown",
                "--dict",
                str(self.fixture),
                "--wordbook",
                str(wordbook_path),
                "--no-remote",
            ]
            input_stream = FakeInput("y\n")
            output_stream = io.StringIO()
            exit_code = cli.main(args, input_stream=input_stream, output_stream=output_stream)
            self.assertEqual(exit_code, 2)

    def test_cli_selects_suggestion(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            wordbook_path = Path(temp_dir) / "wordbook.csv"
            args = [
                "wor",
                "--dict",
                str(self.fixture),
                "--wordbook",
                str(wordbook_path),
                "--no-remote",
            ]
            input_stream = FakeInput("1\ny\n")
            output_stream = io.StringIO()
            exit_code = cli.main(args, input_stream=input_stream, output_stream=output_stream)
            self.assertEqual(exit_code, 0)
            wordbook = Wordbook(wordbook_path)
            entry = wordbook.find("world")
            self.assertIsNotNone(entry)

    def test_cli_loop_saves_and_exits(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            wordbook_path = Path(temp_dir) / "wordbook.csv"
            args = [
                "--loop",
                "--dict",
                str(self.fixture),
                "--wordbook",
                str(wordbook_path),
                "--no-remote",
            ]
            input_stream = FakeInput("hello\ny\nq\n")
            output_stream = io.StringIO()
            exit_code = cli.main(args, input_stream=input_stream, output_stream=output_stream)
            self.assertEqual(exit_code, 0)
            wordbook = Wordbook(wordbook_path)
            entry = wordbook.find("hello")
            self.assertIsNotNone(entry)

    def test_cli_review_updates_due(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            wordbook_path = Path(temp_dir) / "wordbook.csv"
            wordbook = Wordbook(wordbook_path)
            entry = WordbookEntry(
                word="hello",
                lemma="hello",
                pos="interj",
                pronunciation="heh-low",
                definitions_en=["greeting"],
                translations_zh=["ni hao"],
                review_due="2023-01-01T00:00:00+00:00",
            )
            wordbook.upsert(entry)
            args = [
                "--review",
                "--dict",
                str(self.fixture),
                "--wordbook",
                str(wordbook_path),
                "--no-remote",
            ]
            input_stream = FakeInput("5\n")
            output_stream = io.StringIO()
            exit_code = cli.main(args, input_stream=input_stream, output_stream=output_stream)
            self.assertEqual(exit_code, 0)
            updated = wordbook.find("hello")
            self.assertIsNotNone(updated)
            self.assertNotEqual(updated.review_due, "2023-01-01T00:00:00+00:00")

    def test_review_enriches_missing_fields(self):
        class StubProvider:
            def enhance(self, entry):
                return ModelEnhancement(
                    definitions_en=["extra definition"],
                    examples=["Example sentence."],
                    word_forms=["past: greeted"],
                    usage_tips=["Use in greetings."],
                    mnemonics=["Sounds like hello."],
                    model="stub-model",
                    confidence=0.6,
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            wordbook_path = Path(temp_dir) / "wordbook.csv"
            wordbook = Wordbook(wordbook_path)
            entry = WordbookEntry(
                word="hello",
                lemma="hello",
                pos="interj",
                pronunciation="heh-low",
                definitions_en=["greeting"],
                translations_zh=["ni hao"],
                review_due="2023-01-01T00:00:00+00:00",
            )
            wordbook.upsert(entry)
            input_stream = FakeInput("5\n")
            output_stream = io.StringIO()
            result = cli.run_review_session(
                wordbook,
                StubProvider(),
                limit=1,
                input_stream=input_stream,
                output_stream=output_stream,
            )
            self.assertEqual(result.reviewed, 1)
            updated = wordbook.find("hello")
            self.assertIsNotNone(updated)
            self.assertIn("Example sentence.", updated.examples)
            self.assertEqual(updated.model, "stub-model")
            self.assertIn("model", updated.source)


if __name__ == "__main__":
    unittest.main()
