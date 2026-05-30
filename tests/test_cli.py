import io
import tempfile
import unittest
from pathlib import Path

from word_agent import cli
from word_agent.models import DictionaryEntry, ModelEnhancement, WordbookEntry
from word_agent.wordbook import Wordbook


class FakeInput(io.StringIO):
    def isatty(self):
        return True


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.fixture = Path(__file__).parent / "fixtures" / "ecdict_sample.csv"

    def test_parse_args_joins_unquoted_term_tokens(self):
        args = cli.parse_args(["latent", "space"])
        self.assertEqual(args.word, "latent space")

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
                pronunciation="",
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
                    pronunciation="/huh-loh/",
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

    def test_build_entry_preserves_pronunciation(self):
        dict_entry = DictionaryEntry(
            word="hello",
            lemma="hello",
            pos="interj",
            pronunciation="",
            definitions_en=["greeting"],
            translations_zh=["ni hao"],
            source="local:ecdict.csv",
            confidence=0.9,
        )
        existing = WordbookEntry(
            word="hello",
            lemma="hello",
            pos="interj",
            pronunciation="heh-low",
            definitions_en=["greeting"],
            translations_zh=["ni hao"],
        )
        entry = cli.build_wordbook_entry(dict_entry, None, existing)
        self.assertEqual(entry.pronunciation, "heh-low")

    def test_build_entry_uses_model_pronunciation(self):
        dict_entry = DictionaryEntry(
            word="hello",
            lemma="hello",
            pos="interj",
            pronunciation="",
            definitions_en=["greeting"],
            translations_zh=["ni hao"],
            source="local:ecdict.csv",
            confidence=0.9,
        )
        enhancement = ModelEnhancement(
            pronunciation="/huh-loh/",
            model="stub-model",
            confidence=0.6,
        )
        entry = cli.build_wordbook_entry(dict_entry, enhancement, None)
        self.assertEqual(entry.pronunciation, "/huh-loh/")

    def test_maybe_enrich_adds_missing_translation(self):
        class StubProvider:
            def enhance(self, entry):
                return ModelEnhancement(
                    translations_zh=["潜在空间"],
                    model="stub-model",
                    confidence=0.6,
                )

        entry = WordbookEntry(
            word="latent space",
            lemma="latent space",
            pos="term",
            pronunciation="",
            definitions_en=["A representation space."],
            translations_zh=[],
        )
        updated = cli.maybe_enrich_entry(entry, StubProvider(), io.StringIO())
        self.assertTrue(updated)
        self.assertIn("潜在空间", entry.translations_zh)

    def test_lookup_hyphenated_term_uses_model_when_missing_locally(self):
        class StubProvider:
            def enhance(self, entry):
                return ModelEnhancement(
                    definitions_en=["Adapting a pretrained model to a task."],
                    translations_zh=["微调"],
                    examples=["Fine-tuning improves downstream accuracy."],
                    model="stub-model",
                    confidence=0.8,
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            wordbook_path = Path(temp_dir) / "wordbook.csv"
            args = [
                "fine-tuning",
                "--dict",
                str(self.fixture),
                "--wordbook",
                str(wordbook_path),
            ]
            input_stream = FakeInput("y\n")
            output_stream = io.StringIO()
            settings = cli.load_settings()
            settings.dict_path = self.fixture
            settings.wordbook_path = wordbook_path
            dictionary = cli.EcdictDictionary(self.fixture)
            wordbook = Wordbook(wordbook_path)
            result = cli.process_word(
                "fine-tuning",
                cli.parse_args(args),
                settings,
                wordbook,
                dictionary,
                StubProvider(),
                input_stream,
                output_stream,
            )
            self.assertEqual(result.exit_code, 0)
            entry = wordbook.find("fine-tuning")
            self.assertIsNotNone(entry)
            self.assertIn("微调", entry.translations_zh)
            self.assertIn("model:term-lookup", entry.source)

    def test_lookup_term_without_model_does_not_use_dictionary_or_word_parts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            wordbook_path = Path(temp_dir) / "wordbook.csv"
            input_stream = FakeInput("")
            output_stream = io.StringIO()
            settings = cli.load_settings()
            settings.dict_path = self.fixture
            settings.wordbook_path = wordbook_path
            dictionary = cli.EcdictDictionary(self.fixture)
            wordbook = Wordbook(wordbook_path)
            args = cli.parse_args([
                "latent space",
                "--dict",
                str(self.fixture),
                "--wordbook",
                str(wordbook_path),
                "--no-remote",
            ])
            result = cli.process_word(
                "latent space",
                args,
                settings,
                wordbook,
                dictionary,
                None,
                input_stream,
                output_stream,
            )
            self.assertEqual(result.exit_code, 2)
            self.assertIn("local dictionary and word-by-word fallback are disabled", output_stream.getvalue())
            self.assertIsNone(wordbook.find("latent space"))

    def test_lookup_multiword_term_uses_model_without_local_dictionary_lookup(self):
        class StubProvider:
            def enhance(self, entry):
                return ModelEnhancement(
                    definitions_en=["A space of learned latent representations."],
                    translations_zh=["潜在空间"],
                    model="stub-model",
                    confidence=0.8,
                )

        class FailingDictionary:
            def lookup(self, word):
                raise AssertionError("term lookup should not use local dictionary")

            def suggest(self, word):
                raise AssertionError("term lookup should not use local suggestions")

        with tempfile.TemporaryDirectory() as temp_dir:
            wordbook_path = Path(temp_dir) / "wordbook.csv"
            input_stream = FakeInput("n\n")
            output_stream = io.StringIO()
            settings = cli.load_settings()
            settings.dict_path = self.fixture
            settings.wordbook_path = wordbook_path
            wordbook = Wordbook(wordbook_path)
            args = cli.parse_args([
                "latent space",
                "--dict",
                str(self.fixture),
                "--wordbook",
                str(wordbook_path),
            ])
            result = cli.process_word(
                "latent space",
                args,
                settings,
                wordbook,
                FailingDictionary(),
                StubProvider(),
                input_stream,
                output_stream,
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("潜在空间", output_stream.getvalue())

    def test_maybe_enrich_sets_pronunciation_when_missing(self):
        class StubProvider:
            def enhance(self, entry):
                return ModelEnhancement(
                    pronunciation="/huh-loh/",
                    model="stub-model",
                    confidence=0.6,
                )

        entry = WordbookEntry(
            word="hello",
            lemma="hello",
            pos="interj",
            pronunciation="",
            definitions_en=["greeting"],
            translations_zh=["ni hao"],
        )
        updated = cli.maybe_enrich_entry(entry, StubProvider(), io.StringIO())
        self.assertTrue(updated)
        self.assertEqual(entry.pronunciation, "/huh-loh/")


if __name__ == "__main__":
    unittest.main()
