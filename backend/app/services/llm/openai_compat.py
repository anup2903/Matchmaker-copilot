"""OpenAI-compatible chat-completions provider (OpenAI, Azure-style gateways, OpenRouter, vLLM, Ollama, ...).

All vendor-specific HTTP details live here. The API key stays on the server.
"""

import json
import re
from typing import Any

import httpx
from pydantic import ValidationError

from app.schemas.feedback import StructuredFeedback, StructuredSignal
from app.services.domain import PreferenceIn
from app.services.llm.prompts import SYSTEM_PROMPT, build_user_payload
from app.services.llm.provider import InvalidModelOutputError, LLMProvider, LLMUnavailableError

DEFAULT_BASE_URL = "https://api.openai.com/v1"

# Keys that strict structured-output modes commonly reject; the Pydantic model still enforces them afterwards.
_UNSUPPORTED_SCHEMA_KEYS = {"minLength", "maxLength", "minItems", "maxItems", "title", "default", "description"}


def _strip_schema(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _strip_schema(v) for k, v in node.items() if k not in _UNSUPPORTED_SCHEMA_KEYS}
    if isinstance(node, list):
        return [_strip_schema(v) for v in node]
    return node


def _llm_schema() -> dict[str, Any]:
    """The schema shown to the model: `attribute` is derived server-side, so the model is not asked for it."""
    schema = StructuredFeedback.model_json_schema()
    signal = schema.get("$defs", {}).get("StructuredSignal", {})
    signal.get("properties", {}).pop("attribute", None)
    if "required" in signal:
        signal["required"] = [r for r in signal["required"] if r != "attribute"]
    return _strip_schema(schema)


def _json_schema_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {"name": "structured_feedback", "strict": True, "schema": _llm_schema()},
    }


def parse_model_output(raw: str) -> StructuredFeedback:
    """Validate raw model text with Pydantic. Never trust model JSON."""
    text = raw.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidModelOutputError(f"reply was not valid JSON ({exc.msg})", raw=raw) from exc
    if isinstance(data, list):  # tolerate a bare array of signals
        data = {"signals": data}
    if isinstance(data, dict) and isinstance(data.get("signals"), list):
        # Models occasionally add stray keys; drop anything outside the contract rather than fail the note.
        allowed = set(StructuredSignal.model_fields)
        data = {
            "signals": [{k: v for k, v in s.items() if k in allowed} if isinstance(s, dict) else s for s in data["signals"]]
        }
    try:
        return StructuredFeedback.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:6])
        raise InvalidModelOutputError(f"JSON did not match the schema ({problems})", raw=raw) from exc


class OpenAICompatibleProvider(LLMProvider):
    name = "llm"
    demo = False

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "",
        timeout: float = 30.0,
        phrase_timeout: float = 8.0,
        client: httpx.Client | None = None,
    ):
        self._api_key = api_key
        self._model = model
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._phrase_timeout = phrase_timeout
        self._client = client or httpx.Client(timeout=timeout)

    def structure_rejection(
        self,
        note: str,
        client_preferences: list[PreferenceIn],
        correction: str | None = None,
    ) -> StructuredFeedback:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_payload(note, client_preferences)},
        ]
        if correction:
            messages.append({"role": "user", "content": correction})
        return parse_model_output(self._chat(messages))

    def phrase_pattern(self, instruction: str) -> str | None:
        # Best-effort: any failure returns None so the caller keeps the deterministic template.
        messages = [
            {
                "role": "system",
                "content": (
                    "You write one cautious sentence describing a possible behavioural pattern for a "
                    "matchmaker, using ONLY the facts given. Do not add facts, numbers or names. Hedge "
                    "with words like 'may', 'appears to', 'could'. Never say the client is lying, secretly "
                    "wants something, or definitely prefers something. Reply as JSON: {\"sentence\": \"...\"}."
                ),
            },
            {"role": "user", "content": instruction},
        ]
        try:
            raw = self._chat_json(messages)
            data = json.loads(raw)
            sentence = data.get("sentence") if isinstance(data, dict) else None
            return sentence.strip() if isinstance(sentence, str) and sentence.strip() else None
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return None

    def _chat_json(self, messages: list[dict[str, str]]) -> str:
        resp = self._client.post(
            f"{self._base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "messages": messages, "temperature": 0.2, "response_format": {"type": "json_object"}},
            timeout=self._phrase_timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"] or ""

    def _chat(self, messages: list[dict[str, str]]) -> str:
        # Prefer strict schema output; fall back to plain JSON mode for providers that do not support it.
        for response_format in (_json_schema_format(), {"type": "json_object"}):
            payload = {
                "model": self._model,
                "messages": messages,
                "temperature": 0,
                "response_format": response_format,
            }
            try:
                resp = self._client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
            except httpx.TimeoutException as exc:
                raise LLMUnavailableError("The language model timed out.") from exc
            except httpx.HTTPError as exc:
                raise LLMUnavailableError("The language model could not be reached.") from exc

            if resp.status_code in (400, 422) and response_format["type"] == "json_schema":
                continue  # provider rejected response_format; retry once in JSON mode
            if resp.status_code in (401, 403):
                raise LLMUnavailableError("The language model rejected the configured credentials.")
            if resp.status_code >= 400:
                raise LLMUnavailableError(f"The language model returned HTTP {resp.status_code}.")
            try:
                return resp.json()["choices"][0]["message"]["content"] or ""
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise InvalidModelOutputError("unexpected response envelope from provider") from exc
        raise LLMUnavailableError("The language model rejected the request format.")
