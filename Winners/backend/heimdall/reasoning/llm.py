"""Structured-output LLM calls shared by the reasoning components (injectable for tests)."""

import json
import logging
import os
from typing import Optional, Type, TypeVar

import openai
from pydantic import BaseModel

from heimdall.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


CLAUDE_ALIASES = {
    "claude-3-5-sonnet-20241022": "claude-sonnet-4-5-20250929",
    "claude-3-5-sonnet": "claude-sonnet-4-5-20250929",
    "claude-3-7-sonnet": "claude-sonnet-4-6",
    "claude-sonnet": "claude-sonnet-4-5-20250929",
    "claude-3-5-haiku-20241022": "claude-haiku-4-5-20251001",
    "claude-3-5-haiku": "claude-haiku-4-5-20251001",
    "claude-3-haiku-20240307": "claude-haiku-4-5-20251001",
    "claude-haiku": "claude-haiku-4-5-20251001",
    "claude-3-opus-20240229": "claude-opus-4-5-20251101",
    "claude-opus": "claude-opus-4-5-20251101",
}


def resolve_claude_model(name: Optional[str]) -> str:
    if not name:
        return settings.CLAUDE_MODEL
    cleaned = name.strip()
    return CLAUDE_ALIASES.get(cleaned.lower(), cleaned)


class StructuredLLM:
    def __init__(self, model_name: Optional[str] = None, provider: Optional[str] = None):
        if provider:
            self.provider = provider.lower()
        elif model_name and (model_name.lower().startswith("claude") or "anthropic" in model_name.lower()):
            self.provider = "claude"
        elif settings.LLM_PROVIDER.lower() in ("claude", "anthropic"):
            self.provider = "claude"
        else:
            self.provider = "openai"

        if model_name:
            self.model_name = model_name
        elif self.provider == "claude":
            self.model_name = settings.CLAUDE_MODEL
        else:
            self.model_name = settings.OPENAI_REASONING_MODEL or settings.OPENAI_MODEL

        if self.provider == "claude" or self.model_name.lower().startswith("claude"):
            self.model_name = resolve_claude_model(self.model_name)

        self._openai_client: Optional[openai.OpenAI] = None
        self._anthropic_client = None

    @property
    def client(self) -> openai.OpenAI:
        if self._openai_client is None:
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is not configured.")
            self._openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._openai_client

    @property
    def anthropic_client(self):
        if self._anthropic_client is None:
            import anthropic
            api_key = (
                settings.CLAUDE_API_KEY
                or settings.ANTHROPIC_API_KEY
                or os.getenv("CLAUDE_API_KEY")
                or os.getenv("ANTHROPIC_API_KEY")
            )
            if not api_key:
                raise ValueError("CLAUDE_API_KEY or ANTHROPIC_API_KEY is not configured.")
            self._anthropic_client = anthropic.Anthropic(api_key=api_key)
        return self._anthropic_client

    def parse(self, system_prompt: str, user_prompt: str, schema: Type[T]) -> T:
        if self.provider == "claude" or self.model_name.lower().startswith("claude"):
            return self._parse_anthropic(system_prompt, user_prompt, schema)
        return self._parse_openai(system_prompt, user_prompt, schema)

    def _parse_openai(self, system_prompt: str, user_prompt: str, schema: Type[T]) -> T:
        """Structured output via OpenAI, falling back to JSON mode if the parse endpoint fails."""
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        try:
            completion = self.client.beta.chat.completions.parse(
                model=self.model_name, messages=messages, response_format=schema, temperature=0.0)
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raise ValueError(completion.choices[0].message.refusal or "Empty structured response")
            return parsed
        except Exception:
            messages[0]["content"] += ("\nReturn only valid JSON matching this JSON schema:\n"
                                       + json.dumps(schema.model_json_schema()))
            response = self.client.chat.completions.create(
                model=self.model_name, messages=messages, response_format={"type": "json_object"}, temperature=0.0)
            return schema.model_validate(json.loads(response.choices[0].message.content or "{}"))

    def _parse_anthropic(self, system_prompt: str, user_prompt: str, schema: Type[T]) -> T:
        """Structured output via Anthropic Claude with tool use and JSON extraction fallbacks."""
        # 1. Native messages.parse
        try:
            res = self.anthropic_client.messages.parse(
                model=self.model_name,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                output_format=schema,
                max_tokens=4096,
                temperature=0.0,
            )
            if hasattr(res, "parsed_output") and res.parsed_output is not None:
                return res.parsed_output
        except Exception as e:
            logger.debug("Anthropic messages.parse failed: %s; trying tool use", e)

        # 2. Tool use fallback
        tool_name = "record_structured_output"
        tool = {
            "name": tool_name,
            "description": f"Record output conforming to {schema.__name__}",
            "input_schema": schema.model_json_schema(),
        }
        try:
            res = self.anthropic_client.messages.create(
                model=self.model_name,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
                max_tokens=4096,
                temperature=0.0,
            )
            for c in res.content:
                if getattr(c, "type", None) == "tool_use" and getattr(c, "input", None):
                    return schema.model_validate(c.input)
        except Exception as e:
            logger.debug("Anthropic tool calling failed: %s; trying JSON text fallback", e)

        # 3. JSON text parsing fallback
        prompt_with_schema = (
            f"{user_prompt}\n\n"
            f"IMPORTANT: Respond ONLY with a valid JSON object matching this schema:\n"
            f"{json.dumps(schema.model_json_schema())}"
        )
        res = self.anthropic_client.messages.create(
            model=self.model_name,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt_with_schema}],
            max_tokens=4096,
            temperature=0.0,
        )
        content_text = ""
        for c in res.content:
            if hasattr(c, "text") and c.text:
                content_text += c.text
        cleaned = content_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return schema.model_validate(json.loads(cleaned.strip()))

