"""Optional model providers for enrichment."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional

from word_agent.models import DictionaryEntry, ModelEnhancement, WordbookEntry


class ProviderError(RuntimeError):
    pass


GEMINI_DEFAULT_BASE = "https://generativelanguage.googleapis.com"


TERM_PROMPT = (
    "Provide up to 2 short English definitions, up to 3 concise Chinese translations, "
    "and up to 2 example sentences for the given English word or term. For multi-word "
    "academic/scientific terms, translate the whole term instead of translating each word "
    "separately. Also include up to 4 word forms, up to 2 usage tips, and up to 2 "
    "mnemonics. Include IPA pronunciation in 'pronunciation' (use /.../ or leave empty "
    "if unknown). Return strict JSON with keys 'definitions_en', 'translations_zh', "
    "'examples', 'word_forms', 'usage_tips', 'mnemonics', and 'pronunciation'. Use short "
    "labels like 'past: manifested' in word_forms."
)


def _as_list(value: object) -> list:
    if isinstance(value, list):
        return value
    if value is None or value == "":
        return []
    return [value]


def _enhancement_from_parsed(parsed: dict, model: str) -> ModelEnhancement:
    definitions = _as_list(parsed.get("definitions_en"))
    translations = _as_list(parsed.get("translations_zh"))
    examples = _as_list(parsed.get("examples"))
    word_forms = _as_list(parsed.get("word_forms"))
    usage_tips = _as_list(parsed.get("usage_tips"))
    mnemonics = _as_list(parsed.get("mnemonics"))
    pronunciation = str(parsed.get("pronunciation", "")).strip()
    return ModelEnhancement(
        definitions_en=[str(item).strip() for item in definitions if str(item).strip()],
        translations_zh=[str(item).strip() for item in translations if str(item).strip()],
        examples=[str(item).strip() for item in examples if str(item).strip()],
        word_forms=[str(item).strip() for item in word_forms if str(item).strip()],
        usage_tips=[str(item).strip() for item in usage_tips if str(item).strip()],
        mnemonics=[str(item).strip() for item in mnemonics if str(item).strip()],
        pronunciation=pronunciation,
        model=model,
        confidence=0.6,
    )


def _parse_json_content(content: str) -> dict | None:
    cleaned = content.strip()
    if not cleaned:
        return None
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2:
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = cleaned[start : end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                return None
    return None


class OpenAICompatibleProvider:
    def __init__(self, api_base: str, api_key: str, model: str) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model

    def enhance(self, entry: DictionaryEntry) -> ModelEnhancement:
        prompt = TERM_PROMPT
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a concise dictionary assistant."},
                {
                    "role": "user",
                    "content": f"Word: {entry.word}\n" + prompt,
                },
            ],
            "temperature": 0.2,
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.api_base}/v1/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"Remote provider failed with HTTP {exc.code}") from None
        except Exception:
            raise ProviderError("Remote provider failed") from None
        content = self._extract_content(body)
        if not content:
            return ModelEnhancement(model=self.model)
        parsed = _parse_json_content(content)
        if not parsed:
            return ModelEnhancement(model=self.model)
        return _enhancement_from_parsed(parsed, self.model)

    def plan_action(self, state: dict) -> dict | None:
        prompt = (
            "You are a language learning agent. Decide the next action and respond with strict JSON "
            "only. Allowed actions: lookup, review, exit. JSON schema: "
            "{\"action\": \"lookup|review|exit\", \"word\": \"\", \"limit\": 0, \"reason\": \"\"}. "
            "Use \"lookup\" with a word when suggesting a new lookup; leave \"word\" empty to ask the "
            "user. Use \"review\" when there are due items. Use \"exit\" when the session should end."
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a concise study planner."},
                {
                    "role": "user",
                    "content": f"State:\n{json.dumps(state, ensure_ascii=True)}\n{prompt}",
                },
            ],
            "temperature": 0.2,
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.api_base}/v1/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"Remote provider failed with HTTP {exc.code}") from None
        except Exception:
            raise ProviderError("Remote provider failed") from None
        content = self._extract_content(body)
        if not content:
            return None
        parsed = _parse_json_content(content)
        if not isinstance(parsed, dict):
            return None
        return parsed

    def review_coach(self, entry: WordbookEntry) -> dict | None:
        prompt = (
            "Create a short correction tip and a list of 2-4 confusable words for the learner. "
            "Return strict JSON with keys 'review_tip' and 'confusions'. Keep tips under 120 "
            "characters."
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a concise vocabulary coach."},
                {
                    "role": "user",
                    "content": (
                        f"Word: {entry.word}\n"
                        f"Definitions: {entry.definitions_en}\n"
                        f"Translations: {entry.translations_zh}\n"
                        f"{prompt}"
                    ),
                },
            ],
            "temperature": 0.2,
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.api_base}/v1/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"Remote provider failed with HTTP {exc.code}") from None
        except Exception:
            raise ProviderError("Remote provider failed") from None
        content = self._extract_content(body)
        if not content:
            return None
        parsed = _parse_json_content(content)
        if not isinstance(parsed, dict):
            return None
        return parsed

    @staticmethod
    def _extract_content(body: dict) -> str:
        choices = body.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        return message.get("content", "")


class OllamaProvider:
    def __init__(self, api_base: str, model: str) -> None:
        self.api_base = api_base.rstrip("/")
        self.model = model

    def enhance(self, entry: DictionaryEntry) -> ModelEnhancement:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a concise dictionary assistant."},
                {"role": "user", "content": f"Word: {entry.word}\n{TERM_PROMPT}"},
            ],
            "stream": False,
            "options": {"temperature": 0.2},
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.api_base}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"Ollama provider failed with HTTP {exc.code}") from None
        except Exception:
            raise ProviderError("Ollama provider failed") from None
        message = body.get("message") or {}
        content = message.get("content", "")
        if not content:
            return ModelEnhancement(model=self.model)
        parsed = _parse_json_content(content)
        if not parsed:
            return ModelEnhancement(model=self.model)
        return _enhancement_from_parsed(parsed, self.model)


class GeminiProvider:
    def __init__(self, api_base: str, api_key: str, model: str) -> None:
        self.api_base = (api_base or GEMINI_DEFAULT_BASE).rstrip("/")
        self.api_key = api_key
        self.model = model

    def enhance(self, entry: DictionaryEntry) -> ModelEnhancement:
        prompt = TERM_PROMPT
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": f"Word: {entry.word}\n{prompt}"},
                    ],
                }
            ],
            "generationConfig": {"temperature": 0.2},
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.api_base}/v1beta/models/{self.model}:generateContent?key={self.api_key}",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"Remote provider failed with HTTP {exc.code}") from None
        except Exception:
            raise ProviderError("Remote provider failed") from None
        content = self._extract_text(body)
        if not content:
            return ModelEnhancement(model=self.model)
        parsed = _parse_json_content(content)
        if not parsed:
            return ModelEnhancement(model=self.model)
        return _enhancement_from_parsed(parsed, self.model)

    def plan_action(self, state: dict) -> dict | None:
        prompt = (
            "You are a language learning agent. Decide the next action and respond with strict JSON "
            "only. Allowed actions: lookup, review, exit. JSON schema: "
            "{\"action\": \"lookup|review|exit\", \"word\": \"\", \"limit\": 0, \"reason\": \"\"}. "
            "Use \"lookup\" with a word when suggesting a new lookup; leave \"word\" empty to ask the "
            "user. Use \"review\" when there are due items. Use \"exit\" when the session should end."
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": f"State:\n{json.dumps(state, ensure_ascii=True)}\n{prompt}"},
                    ],
                }
            ],
            "generationConfig": {"temperature": 0.2},
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.api_base}/v1beta/models/{self.model}:generateContent?key={self.api_key}",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"Remote provider failed with HTTP {exc.code}") from None
        except Exception:
            raise ProviderError("Remote provider failed") from None
        content = self._extract_text(body)
        if not content:
            return None
        parsed = _parse_json_content(content)
        if not isinstance(parsed, dict):
            return None
        return parsed

    def review_coach(self, entry: WordbookEntry) -> dict | None:
        prompt = (
            "Create a short correction tip and a list of 2-4 confusable words for the learner. "
            "Return strict JSON with keys 'review_tip' and 'confusions'. Keep tips under 120 "
            "characters."
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                f"Word: {entry.word}\n"
                                f"Definitions: {entry.definitions_en}\n"
                                f"Translations: {entry.translations_zh}\n"
                                f"{prompt}"
                            )
                        },
                    ],
                }
            ],
            "generationConfig": {"temperature": 0.2},
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.api_base}/v1beta/models/{self.model}:generateContent?key={self.api_key}",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"Remote provider failed with HTTP {exc.code}") from None
        except Exception:
            raise ProviderError("Remote provider failed") from None
        content = self._extract_text(body)
        if not content:
            return None
        parsed = _parse_json_content(content)
        if not isinstance(parsed, dict):
            return None
        return parsed

    @staticmethod
    def _extract_text(body: dict) -> str:
        candidates = body.get("candidates") or []
        if not candidates:
            return ""
        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        if not parts:
            return ""
        return parts[0].get("text", "")


def get_provider(
    provider: str, api_base: str, api_key: str, model: str
) -> Optional[OpenAICompatibleProvider | GeminiProvider | OllamaProvider]:
    provider_key = provider.lower()
    if provider_key in {"ollama", "local-ollama"}:
        if api_base and model:
            return OllamaProvider(api_base=api_base, model=model)
        return None
    if not provider or not api_base or not api_key or not model:
        if provider and api_key and model and provider_key in {"gemini", "google", "google-gemini"}:
            return GeminiProvider(api_base=api_base, api_key=api_key, model=model)
        return None
    if provider_key in {"openai", "openai-compatible", "compatible"}:
        return OpenAICompatibleProvider(api_base=api_base, api_key=api_key, model=model)
    if provider_key in {"gemini", "google", "google-gemini"}:
        return GeminiProvider(api_base=api_base, api_key=api_key, model=model)
    return None
