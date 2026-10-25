"""Structured-output LLM calls shared by the reasoning components (injectable for tests)."""

import json
from typing import Optional, Type, TypeVar

import openai
from pydantic import BaseModel

from agent_1.config import settings

T = TypeVar("T", bound=BaseModel)


class StructuredLLM:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.OPENAI_REASONING_MODEL or settings.OPENAI_MODEL
        self._client: Optional[openai.OpenAI] = None

    @property
    def client(self) -> openai.OpenAI:
        if self._client is None:
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is not configured.")
            self._client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    def parse(self, system_prompt: str, user_prompt: str, schema: Type[T]) -> T:
        """Structured output, falling back to JSON mode if the parse endpoint fails."""
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
