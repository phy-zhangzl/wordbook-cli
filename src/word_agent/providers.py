"""Optional model providers for enrichment."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict
from typing import Optional

from word_agent.models import DictionaryEntry, ModelEnhancement


class ProviderError(RuntimeError):
    pass


GEMINI_DEFAULT_BASE = "https://generativelanguage.googleapis.com"


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
        prompt = (
            "Provide up to 2 short English definitions and up to 2 example sentences "
            "for the given word. Also include up to 4 word forms, up to 2 usage tips, "
            "and up to 2 mnemonics. Return strict JSON with keys "
            "'definitions_en', 'examples', 'word_forms', 'usage_tips', and 'mnemonics'. "
            "Use short labels like 'past: manifested' in word_forms."
        )
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
        definitions = parsed.get("definitions_en", []) or []
        examples = parsed.get("examples", []) or []
        word_forms = parsed.get("word_forms", []) or []
        usage_tips = parsed.get("usage_tips", []) or []
        mnemonics = parsed.get("mnemonics", []) or []
        return ModelEnhancement(
            definitions_en=[str(item).strip() for item in definitions if str(item).strip()],
            examples=[str(item).strip() for item in examples if str(item).strip()],
            word_forms=[str(item).strip() for item in word_forms if str(item).strip()],
            usage_tips=[str(item).strip() for item in usage_tips if str(item).strip()],
            mnemonics=[str(item).strip() for item in mnemonics if str(item).strip()],
            model=self.model,
            confidence=0.6,
        )

    @staticmethod
    def _extract_content(body: dict) -> str:
        choices = body.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        return message.get("content", "")


class GeminiProvider:
    def __init__(self, api_base: str, api_key: str, model: str) -> None:
        self.api_base = (api_base or GEMINI_DEFAULT_BASE).rstrip("/")
        self.api_key = api_key
        self.model = model

    def enhance(self, entry: DictionaryEntry) -> ModelEnhancement:
        prompt = (
            "Provide up to 2 short English definitions and up to 2 example sentences "
            "for the given word. Also include up to 4 word forms, up to 2 usage tips, "
            "and up to 2 mnemonics. Return strict JSON with keys "
            "'definitions_en', 'examples', 'word_forms', 'usage_tips', and 'mnemonics'. "
            "Use short labels like 'past: manifested' in word_forms."
        )
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
        definitions = parsed.get("definitions_en", []) or []
        examples = parsed.get("examples", []) or []
        word_forms = parsed.get("word_forms", []) or []
        usage_tips = parsed.get("usage_tips", []) or []
        mnemonics = parsed.get("mnemonics", []) or []
        return ModelEnhancement(
            definitions_en=[str(item).strip() for item in definitions if str(item).strip()],
            examples=[str(item).strip() for item in examples if str(item).strip()],
            word_forms=[str(item).strip() for item in word_forms if str(item).strip()],
            usage_tips=[str(item).strip() for item in usage_tips if str(item).strip()],
            mnemonics=[str(item).strip() for item in mnemonics if str(item).strip()],
            model=self.model,
            confidence=0.6,
        )

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
) -> Optional[OpenAICompatibleProvider | GeminiProvider]:
    if not provider or not api_base or not api_key or not model:
        if provider and api_key and model and provider.lower() in {"gemini", "google", "google-gemini"}:
            return GeminiProvider(api_base=api_base, api_key=api_key, model=model)
        return None
    if provider.lower() in {"openai", "openai-compatible", "compatible"}:
        return OpenAICompatibleProvider(api_base=api_base, api_key=api_key, model=model)
    if provider.lower() in {"gemini", "google", "google-gemini"}:
        return GeminiProvider(api_base=api_base, api_key=api_key, model=model)
    return None
