"""DeepSeek chat client (OpenAI-compatible endpoint)."""

from __future__ import annotations

from .config import DEEPSEEK_BASE_URL, LLM_MODEL, Settings
from .mock import mock_llm
from .prompts import SYSTEM_PROMPT
from .util import with_retries


class LLMError(RuntimeError):
    pass


class PitchGenerator:
    def __init__(self, settings: Settings, temperature: float = 0.3, max_tokens: int = 500):
        self.settings = settings
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = None

    def _live_client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.settings.key("deepseek_api_key"),
                base_url=DEEPSEEK_BASE_URL,
                timeout=60.0,
                max_retries=0,  # our own retry wrapper handles transient errors
            )
        return self._client

    def generate(self, prompt: str) -> str:
        if self.settings.is_mock:
            return mock_llm(prompt)

        def call() -> str:
            response = self._live_client().chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            content = response.choices[0].message.content
            if not content:
                raise LLMError("DeepSeek returned an empty completion")
            return content.strip()

        return with_retries(call, attempts=3, base_delay=2.0)
