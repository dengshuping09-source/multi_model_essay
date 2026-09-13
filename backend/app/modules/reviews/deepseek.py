from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.modules.reviews.contracts import (
    EssayReviewOutput,
    ensure_chinese_review_feedback,
    parse_essay_review_output,
)

PROMPT_VERSION = "essay-review-v5-quick-focused-feedback"
QUICK_REVIEW_MAX_OUTPUT_TOKENS = 1_200


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


class ProviderNetworkError(DeepSeekReviewError):
    pass


class ProviderRateLimitError(DeepSeekReviewError):
    pass


class ProviderServiceError(DeepSeekReviewError):
    pass


@dataclass(frozen=True)
class ProviderReviewResult:
    output: EssayReviewOutput
    provider_response_id: str | None
    model_name: str
    usage: dict[str, int] | None
    timing: dict[str, int] | None = None


SYSTEM_PROMPT = """你是一位有经验的中小学语文老师。请独立、简洁地判断这篇作文的核心表现。

只返回一个 JSON 对象，结构如下（JSON 字段名和枚举值必须保持英文；所有解释性文字使用自然、简体中文）：
{
  "overall_score": "四个维度分数之和",
  "summary": "一句简短整体判断",
  "dimension_scores": [
    {"dimension":"content_and_ideas","score":0-25,"max_score":25,"rationale":"简短理由","evidence":[{"quote":"原文准确片段","rationale":"简短依据"}]},
    {"dimension":"structure_and_coherence","score":0-25,"max_score":25,"rationale":"简短理由","evidence":[]},
    {"dimension":"language_and_expression","score":0-25,"max_score":25,"rationale":"简短理由","evidence":[]},
    {"dimension":"writing_conventions","score":0-25,"max_score":25,"rationale":"简短理由","evidence":[]}
  ],
  "annotations": [
    {"category":"content|structure|language|expression|conventions","kind":"improvement|strength","issue_type":"typo|grammar|punctuation|wording|sentence|other","severity":"low|medium|high","quote":"原文准确片段","comment":"这里怎么看或好在哪里","suggestion":"可以怎么改或为什么值得保留"}
  ],
  "improvement_suggestions": [
    {"priority":"low|medium|high","category":"content|structure|language|expression|conventions","suggestion":"一条可执行的核心建议"}
  ]
}

四个必填维度各出现一次。每项理由保持简短；每个维度最多一处原文依据；最多三条修改建议；最多两条最重要的原文定位反馈。引用必须从原文逐字复制。不要做全文逐句扫描、全文表达检查、润色、长示例或技术说明，也不要虚构原文没有的事实。若原文主要是中文，除 quote 原文引用外，所有说明、总评和建议都必须使用自然、简体中文。"""


class DeepSeekReviewClient:
    async def review(self, essay_text: str, context_instruction: str | None = None) -> ProviderReviewResult:
        api_key = settings.deepseek_api_key
        if api_key is None:
            raise DeepSeekConfigurationError("DEEPSEEK_API_KEY is not configured")

        payload = {
            "model": settings.deepseek_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{context_instruction or ''}\n\n待评作文：\n{essay_text}"},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": min(settings.deepseek_max_output_tokens, QUICK_REVIEW_MAX_OUTPUT_TOKENS),
            "temperature": 0,
            "stream": False,
        }
        timeout = httpx.Timeout(settings.model_review_timeout_seconds, connect=10.0)
        endpoint = settings.deepseek_api_url or f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
        started_at = perf_counter()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    endpoint,
                    headers={"Authorization": f"Bearer {api_key.get_secret_value()}"},
                    json=payload,
                ) as response:
                    first_response_ms = round((perf_counter() - started_at) * 1000)
                    await response.aread()
        except httpx.TimeoutException as exc:
            raise DeepSeekTimeoutError("DeepSeek review request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderNetworkError("DeepSeek review request could not be completed") from exc
        completed_ms = round((perf_counter() - started_at) * 1000)

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
            output = ensure_chinese_review_feedback(
                essay_text, parse_essay_review_output(content)
            )
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
            raise DeepSeekResponseFormatError(
                _safe_format_error("DeepSeek", exc)
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
            timing={"first_response_ms": first_response_ms, "completed_ms": completed_ms},
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
        return ProviderRateLimitError(f"{provider_name} request was rate limited (HTTP 429)")
    if status_code >= 500:
        return ProviderServiceError(f"{provider_name} provider service failed (HTTP {status_code})")
    return DeepSeekReviewError(f"{provider_name} review request was rejected (HTTP {status_code})")


def _safe_format_error(provider_name: str, error: Exception) -> str:
    """Describe schema drift without persisting model text or field values."""
    if isinstance(error, ValidationError):
        paths = [".".join(str(part) for part in item["loc"]) for item in error.errors()[:4]]
        location = ", ".join(paths) or "unknown field"
        return f"{provider_name} returned invalid review fields: {location}"
    if isinstance(error, (KeyError, IndexError, TypeError)):
        return f"{provider_name} response envelope was incomplete"
    return f"{provider_name} returned malformed review JSON"
