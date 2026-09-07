from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Literal

import httpx
from pydantic import SecretStr, ValidationError

from app.core.config import settings
from app.modules.reviews.contracts import EssayPolishOutput


class PolishGenerationError(RuntimeError):
    """A safe error raised when a teaching-oriented polish cannot be generated."""


class PolishProviderUnavailableError(PolishGenerationError):
    pass


class PolishResponseFormatError(PolishGenerationError):
    pass


@dataclass(frozen=True)
class PolishBackend:
    style: Literal["chat", "responses"]
    endpoint: str
    model: str
    api_key: SecretStr


POLISH_SYSTEM_PROMPT = """你是一位耐心的中小学语文老师。请在保留学生原意、事实、结构和个人语气的前提下，对作文做克制的表达润色。

必须遵守：
1. 不新增原文没有的人物、事件、观点或事实。
2. 不把作文重写成范文，只修改确实影响表达的词句、细节衔接和书写规范。
3. 保留原文段落顺序，尽量控制修改数量。
4. 每项修改都要引用原文中真实存在的连续片段，并给出修改后的对应片段和学生能理解的原因。
5. 只返回一个 JSON 对象，不要输出 Markdown。

JSON 结构必须是：
{
  "polished_text": "保留原意和结构的完整润色稿",
  "overview": "一句话说明这次润色主要改善了什么",
  "changes": [
    {
      "original": "原文中的真实连续片段",
      "revised": "对应的修改后片段",
      "reason": "为什么这样修改",
      "category": "wording|sentence|detail|structure|conventions"
    }
  ]
}
"""


def _chat_endpoint(base_url: str, explicit_url: str | None = None) -> str:
    if explicit_url:
        return explicit_url
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/chat/completions") else f"{normalized}/chat/completions"


def _responses_endpoint(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/responses") else f"{normalized}/responses"


def _configured_backends() -> list[PolishBackend]:
    backends: list[PolishBackend] = []
    if settings.deepseek_api_key is not None:
        backends.append(
            PolishBackend(
                style="chat",
                endpoint=_chat_endpoint(settings.deepseek_base_url, settings.deepseek_api_url),
                model=settings.deepseek_model,
                api_key=settings.deepseek_api_key,
            )
        )
    if settings.qwen_api_key is not None:
        backends.append(
            PolishBackend(
                style="chat",
                endpoint=_chat_endpoint(settings.qwen_base_url),
                model=settings.qwen_model,
                api_key=settings.qwen_api_key,
            )
        )
    doubao_key = settings.ark_api_key or settings.doubao_api_key
    doubao_base_url = settings.ark_base_url if settings.ark_api_key is not None else settings.doubao_base_url
    if doubao_key is not None and doubao_base_url:
        backends.append(
            PolishBackend(
                style="responses",
                endpoint=_responses_endpoint(doubao_base_url),
                model=settings.ark_model if settings.ark_api_key is not None else settings.doubao_model,
                api_key=doubao_key,
            )
        )
    return backends


def _extract_json_text(response_data: dict[str, Any], style: Literal["chat", "responses"]) -> str:
    if style == "chat":
        content = response_data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty response")
        return content.strip()

    direct_text = response_data.get("output_text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()
    for output in response_data.get("output", []):
        if not isinstance(output, dict):
            continue
        for content in output.get("content", []):
            if isinstance(content, dict) and isinstance(content.get("text"), str) and content["text"].strip():
                return content["text"].strip()
    raise ValueError("empty response")


def _strip_code_fence(content: str) -> str:
    normalized = content.strip()
    if not normalized.startswith("```"):
        return normalized
    first_newline = normalized.find("\n")
    if first_newline >= 0:
        normalized = normalized[first_newline + 1 :]
    if normalized.endswith("```"):
        normalized = normalized[:-3]
    return normalized.strip()


def validate_polish(original_text: str, output: EssayPolishOutput) -> EssayPolishOutput:
    original = original_text.strip()
    polished = output.polished_text.strip()
    length_ratio = len(polished) / max(len(original), 1)
    similarity = SequenceMatcher(None, original, polished, autojunk=False).ratio()
    if not 0.6 <= length_ratio <= 1.5 or similarity < 0.42:
        raise PolishResponseFormatError("润色结果改动过大，已为你保留原文，请稍后重试")

    seen: set[str] = set()
    for change in output.changes:
        if change.original not in original or change.revised not in polished:
            raise PolishResponseFormatError("润色结果与原文无法可靠对照，请稍后重试")
        if change.original in seen:
            raise PolishResponseFormatError("润色结果包含重复修改，请稍后重试")
        seen.add(change.original)
    return output.model_copy(update={"polished_text": polished})


async def generate_polish(
    essay_text: str,
    summary: str | None,
    suggestions: list[str],
) -> EssayPolishOutput:
    backends = _configured_backends()
    if not backends:
        raise PolishProviderUnavailableError("润色服务暂未配置")

    guidance = "\n".join(f"- {item}" for item in suggestions[:5]) or "- 优先改善表达清晰度"
    user_prompt = (
        f"评测总评：{summary or '暂无'}\n"
        f"优先建议：\n{guidance}\n\n"
        f"学生原文：\n{essay_text}"
    )
    last_error: PolishGenerationError | None = None
    for backend in backends:
        if backend.style == "chat":
            payload = {
                "model": backend.model,
                "messages": [
                    {"role": "system", "content": POLISH_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": settings.deepseek_max_output_tokens,
                "temperature": 0.2,
                "stream": False,
            }
        else:
            payload = {
                "model": backend.model,
                "instructions": POLISH_SYSTEM_PROMPT,
                "input": user_prompt,
                "max_output_tokens": settings.deepseek_max_output_tokens,
                "temperature": 0.2,
                "store": False,
            }

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.model_review_timeout_seconds, connect=10.0)
            ) as client:
                response = await client.post(
                    backend.endpoint,
                    headers={"Authorization": f"Bearer {backend.api_key.get_secret_value()}"},
                    json=payload,
                )
            if response.is_error:
                last_error = PolishGenerationError("润色请求暂未完成")
                continue
            response_data: dict[str, Any] = response.json()
            content = _strip_code_fence(_extract_json_text(response_data, backend.style))
            output = EssayPolishOutput.model_validate(json.loads(content))
            return validate_polish(essay_text, output)
        except httpx.TimeoutException:
            last_error = PolishGenerationError("润色生成超时，请稍后重试")
        except httpx.HTTPError:
            last_error = PolishGenerationError("润色服务暂时无法连接")
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError, ValidationError):
            last_error = PolishResponseFormatError("润色结果格式不完整，请稍后重试")

    raise last_error or PolishGenerationError("润色暂未完成，请稍后重试")
