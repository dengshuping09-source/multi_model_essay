from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.modules.reviews.contracts import EssayReviewOutput, parse_essay_review_output

PROMPT_VERSION = "essay-review-v2"


class DeepSeekReviewError(RuntimeError):
    """A provider failure with a safe message suitable for persistence and APIs."""


class DeepSeekConfigurationError(DeepSeekReviewError):
    pass


class DeepSeekTimeoutError(DeepSeekReviewError):
    pass


class ProviderAuthenticationError(DeepSeekReviewError):
    pass


class ProviderModelOrEndpointError(DeepSeekReviewError):
    pass


class DeepSeekResponseFormatError(DeepSeekReviewError):
    pass


@dataclass(frozen=True)
class ProviderReviewResult:
    output: EssayReviewOutput
    provider_response_id: str | None
    model_name: str
    usage: dict[str, int] | None


SYSTEM_PROMPT = """You are an experienced Chinese composition teacher. Review the supplied Chinese essay fairly and constructively.

Return only one JSON object. The output must satisfy this exact contract:
{
  "overall_score": 0-100 number equal to the four dimension scores summed,
  "summary": "concise overall evaluation",
  "dimension_scores": [
    {"dimension":"content_and_ideas","score":0-25,"max_score":25,"rationale":"...","evidence":[{"quote":"exact excerpt from essay","rationale":"...","start_offset":0,"end_offset":2}]},
    {"dimension":"structure_and_coherence","score":0-25,"max_score":25,"rationale":"...","evidence":[...]},
    {"dimension":"language_and_expression","score":0-25,"max_score":25,"rationale":"...","evidence":[...]},
    {"dimension":"writing_conventions","score":0-25,"max_score":25,"rationale":"...","evidence":[...]}
  ],
  "annotations": [
    {"category":"content|structure|language|expression|conventions","kind":"improvement|strength","issue_type":"typo|grammar|punctuation|wording|sentence|other","severity":"low|medium|high","quote":"exact excerpt from essay","start_offset":0,"end_offset":2,"comment":"specific feedback","suggestion":"specific revision advice or why this strength should be kept"}
  ],
  "improvement_suggestions": [
    {"priority":"low|medium|high","category":"content|structure|language|expression|conventions","suggestion":"actionable advice","example_revision":"optional example"}
  ]
}

Use each required dimension exactly once. Annotations must include both useful improvements and genuinely strong sentences when present. Mark positive annotations with kind=strength and explain why the expression, description, or structure works; do not invent praise. Use issue_type only for improvement annotations to distinguish typos, grammar or ill-formed sentences, punctuation, wording, and other sentence-level issues. Every evidence quote and annotation quote must be copied exactly from the essay. Offset values are zero-based character offsets; omit both offsets if you cannot provide an exact range. Do not invent facts, author identity, or external context. JSON is required."""


class DeepSeekReviewClient:
    async def review(self, essay_text: str, context_instruction: str | None = None) -> ProviderReviewResult:
        api_key = settings.deepseek_api_key
        if api_key is None:
            raise DeepSeekConfigurationError("DEEPSEEK_API_KEY is not configured")

        payload = {
            "model": settings.deepseek_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{context_instruction or ''}\n\nEssay to review:\n{essay_text}"},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": settings.deepseek_max_output_tokens,
            "stream": False,
        }
        timeout = httpx.Timeout(settings.deepseek_timeout_seconds, connect=10.0)
        endpoint = settings.deepseek_api_url or f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {api_key.get_secret_value()}"},
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise DeepSeekTimeoutError("DeepSeek review request timed out") from exc
        except httpx.HTTPError as exc:
            raise DeepSeekReviewError("DeepSeek review request could not be completed") from exc

        if response.is_error:
            raise provider_http_error("DeepSeek", response)

        try:
            response_data: dict[str, Any] = response.json()
            choice = response_data["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise DeepSeekResponseFormatError("DeepSeek response was incomplete")
            content = choice["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise DeepSeekResponseFormatError("DeepSeek returned an empty review")
            output = parse_essay_review_output(content)
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
            raise DeepSeekResponseFormatError(
                "DeepSeek returned a review with an invalid structure"
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
                else settings.deepseek_model
            ),
            usage=usage,
        )


def get_deepseek_client() -> DeepSeekReviewClient:
    return DeepSeekReviewClient()


def provider_http_error(provider_name: str, response: httpx.Response) -> DeepSeekReviewError:
    """Return a persistable, credential-safe classification for a provider HTTP error."""
    status_code = response.status_code
    error_code: str | None = None
    try:
        payload = response.json()
        error = payload.get("error") if isinstance(payload, dict) else None
        candidate = error.get("code") if isinstance(error, dict) else None
        error_code = candidate if isinstance(candidate, str) else None
    except ValueError:
        pass
    if status_code in {401, 403}:
        return ProviderAuthenticationError(f"{provider_name} API key was rejected (HTTP {status_code})")
    if error_code == "ModelNotOpen":
        return ProviderModelOrEndpointError(
            f"{provider_name} configured model is not activated for this account (ModelNotOpen)"
        )
    if error_code in {"ModelNotFound", "InvalidModel", "ModelNotExist"}:
        return ProviderModelOrEndpointError(
            f"{provider_name} configured model was not found ({error_code})"
        )
    if status_code == 404:
        return ProviderModelOrEndpointError(
            f"{provider_name} model or endpoint was not found (HTTP 404)"
        )
    if status_code == 429:
        return DeepSeekReviewError(f"{provider_name} request was rate limited (HTTP 429)")
    if status_code >= 500:
        return DeepSeekReviewError(f"{provider_name} provider service failed (HTTP {status_code})")
    return DeepSeekReviewError(f"{provider_name} review request was rejected (HTTP {status_code})")
