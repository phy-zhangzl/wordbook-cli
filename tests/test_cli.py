import io
import tempfile
import unittest
from pathlib import Path

from word_agent import cli
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


if __name__ == "__main__":
    unittest.main()
