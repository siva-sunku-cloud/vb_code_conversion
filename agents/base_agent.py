from abc import ABC, abstractmethod
from typing import Optional
import json

import anthropic

from config import Config
from utils.logger import get_logger


class BaseAgent(ABC):
    """Abstract base for every spoke agent in the pipeline."""

    def __init__(self, name: str, model: Optional[str] = None):
        self.name = name
        self.model = model or Config.AGENT_MODEL
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.logger = get_logger(name)

    # ── LLM helpers ──────────────────────────────────────────────────────────

    def _call_llm(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
        tools: Optional[list] = None,
    ) -> anthropic.types.Message:
        """Single Claude API call with prompt caching on the system prompt."""
        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = self.client.messages.create(**kwargs)
        self.logger.debug(
            f"tokens used — input: {response.usage.input_tokens}, "
            f"output: {response.usage.output_tokens}"
        )
        return response

    def _text(self, response: anthropic.types.Message) -> str:
        """Extract the first text block from a response."""
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""

    def _parse_json(self, response: anthropic.types.Message) -> dict:
        """Extract and parse JSON from a response, stripping markdown fences."""
        raw = self._text(response).strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]
        return json.loads(raw)
