from typing import Any

from app.core.config import settings
from app.infrastructure.llm.qwen_client import qwen
from app.services.nl2sql.generator import MockCandidateSqlProvider


class DisabledCandidateSqlProvider:
    def generate(self, prompt: str) -> str:
        raise RuntimeError("NL2SQL provider is disabled")


class QwenCandidateSqlProvider:
    def __init__(self, client: Any | None = None, timeout_seconds: int | None = None) -> None:
        self.client = client or qwen
        self.timeout_seconds = timeout_seconds or settings.qwen_nl2sql_timeout_seconds

    def generate(self, prompt: str) -> str:
        if not getattr(self.client, "available", False):
            raise RuntimeError("Qwen provider is not configured")

        messages = [{"role": "user", "content": prompt}]
        try:
            response = self.client.chat(messages, temperature=0.0, timeout_seconds=self.timeout_seconds)
        except TypeError:
            response = self.client.chat(messages, temperature=0.0)

        if not response.get("available", False):
            raise RuntimeError(response.get("message") or "Qwen provider is not configured")
        content = response.get("content")
        if content is None:
            raise RuntimeError(response.get("message") or "Qwen provider returned empty content")
        return str(content)


def build_candidate_sql_provider(
    provider_name: str | None = None,
    mock_output: str | None = None,
    qwen_client: Any | None = None,
):
    name = (provider_name or settings.nl2sql_provider).lower()
    if name == "mock":
        return MockCandidateSqlProvider(mock_output)
    if name == "qwen":
        return QwenCandidateSqlProvider(qwen_client)
    if name == "disabled":
        return DisabledCandidateSqlProvider()
    raise ValueError(f"unsupported NL2SQL provider: {name}")
