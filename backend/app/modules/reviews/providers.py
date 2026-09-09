from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from pydantic import SecretStr, ValidationError

from app.core.config import settings
from app.modules.reviews.contracts import EssayReviewOutput, parse_essay_review_output
from app.modules.reviews.deepseek import (
    DeepSeekReviewError,
    DeepSeekResponseFormatError,
    ProviderReviewResult,
    QUICK_REVIEW_MAX_OUTPUT_TOKENS,
    SYSTEM_PROMPT,
    get_deepseek_client,
    provider_http_error,
)
from app.modules.reviews.standards import EssayReviewContext, scoring_instruction


class ProviderUnavailableError(DeepSeekReviewError):
    pass


@dataclass(frozen=True)
class ProviderStatus:
    key: str
    display_name: str
    model_name: str
    configured: bool
    detail: str


class ReviewProvider(Protocol):
    key: str
    display_name: str
    model_name: str

    def status(self) -> ProviderStatus: ...

    async def review(self, essay_text: str, context: EssayReviewContext) -> ProviderReviewResult: ...


class DeepSeekProvider:
    key = "deepseek"
    display_name = "DeepSeek"

    @property
    def model_name(self) -> str:
        return settings.deepseek_model

    def status(self) -> ProviderStatus:
        configured = _has_value(settings.deepseek_api_key)
        return ProviderStatus(
            key=self.key,
            display_name=self.display_name,
            model_name=self.model_name,
            configured=configured,
            detail="ready" if configured else "DEEPSEEK_API_KEY is not configured",
        )

    async def review(self, essay_text: str, context: EssayReviewContext) -> ProviderReviewResult:
        return await get_deepseek_client().review(essay_text, scoring_instruction(context, essay_text))


class OpenAiCompatibleProvider:
    """Adapter for providers exposing the OpenAI chat-completions wire format."""

    def __init__(
        self,
        key: str,
        display_name: str,
        model_name: str,
        api_key: SecretStr | None,
        base_url: str | None,
    ) -> None:
        self.key = key
        self.display_name = display_name
        self.model_name = model_name
        self._api_key = api_key
        self._base_url = base_url

    def status(self) -> ProviderStatus:
        configured = _has_value(self._api_key) and bool(self._base_url)
        return ProviderStatus(
            key=self.key,
            display_name=self.display_name,
            model_name=self.model_name,
            configured=configured,
            detail="ready" if configured else f"{self.key.upper()} API credentials are not configured",
        )

    async def review(self, essay_text: str, context: EssayReviewContext) -> ProviderReviewResult:
        state = self.status()
        if not state.configured:
            raise ProviderUnavailableError(state.detail)
        base_url = (self._base_url or "").rstrip("/")
        endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"{scoring_instruction(context, essay_text)}\n\nEssay to review:\n{essay_text}",
                },
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": min(settings.deepseek_max_output_tokens, QUICK_REVIEW_MAX_OUTPUT_TOKENS),
            "temperature": 0,
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.model_review_timeout_seconds, connect=10.0)
            ) as client:
                response = await client.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {self._api_key.get_secret_value()}"},
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError(f"{self.display_name} review request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"{self.display_name} review request could not be completed") from exc
        if response.is_error:
            raise provider_http_error(self.display_name, response)
        try:
            response_data: dict[str, Any] = response.json()
            content = response_data["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("empty content")
            output = parse_essay_review_output(content)
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
            raise DeepSeekResponseFormatError(
                f"{self.display_name} returned a review with an invalid structure"
            ) from exc
        raw_usage = response_data.get("usage")
        usage = (
            {
                key: value
                for key, value in raw_usage.items()
                if key in {"prompt_tokens", "completion_tokens", "total_tokens"}
                and isinstance(value, int)
            }
            if isinstance(raw_usage, dict)
            else None
        )
        return ProviderReviewResult(
            output=output,
            provider_response_id=(
                response_data.get("id") if isinstance(response_data.get("id"), str) else None
            ),
            model_name=(
                response_data.get("model")
                if isinstance(response_data.get("model"), str)
                else self.model_name
            ),
            usage=usage,
        )


class ArkResponsesProvider(OpenAiCompatibleProvider):
    """Ark uses the OpenAI-compatible chat-completions endpoint for text reviews.

    The former `/responses` request returned 404 for the configured Ark v3
    account.  Using the compatible endpoint also lets the provider return the
    account's precise `ModelNotOpen` classification instead of a misleading
    generic endpoint failure.
    """

    async def review(self, essay_text: str, context: EssayReviewContext) -> ProviderReviewResult:
        return await super().review(essay_text, context)


def get_review_provider_registry() -> dict[str, ReviewProvider]:
    return {
        "deepseek": DeepSeekProvider(),
        "qwen": OpenAiCompatibleProvider(
            "qwen", "Qwen", settings.qwen_model, settings.qwen_api_key, settings.qwen_base_url
        ),
        "doubao": ArkResponsesProvider(
            "doubao",
            "豆包",
            settings.ark_model if settings.ark_api_key is not None else settings.doubao_model,
            settings.ark_api_key or settings.doubao_api_key,
            settings.ark_base_url if settings.ark_api_key is not None else settings.doubao_base_url,
        ),
    }


def _has_value(secret: SecretStr | None) -> bool:
    return secret is not None and bool(secret.get_secret_value().strip())
