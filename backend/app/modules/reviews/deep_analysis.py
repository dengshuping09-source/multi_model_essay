from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import SecretStr, ValidationError

from app.core.config import settings
from app.modules.reviews.contracts import DeepAnalysisOutput, parse_json_object


class DeepAnalysisGenerationError(RuntimeError):
    """A credential-safe error for optional report enrichment."""


class DeepAnalysisProviderUnavailableError(DeepAnalysisGenerationError):
    pass


class DeepAnalysisResponseFormatError(DeepAnalysisGenerationError):
    pass


@dataclass(frozen=True)
class DeepAnalysisBackend:
    key: str
    endpoint: str
    model: str
    api_key: SecretStr


@dataclass(frozen=True)
class DeepAnalysisProviderResult:
    output: DeepAnalysisOutput
    provider_key: str
    model_name: str


DEEP_ANALYSIS_PROMPT_VERSION = "essay-deep-analysis-v1"

DEEP_ANALYSIS_SYSTEM_PROMPT = """你是一位耐心、严谨的中小学语文老师。核心评分已经由多个独立评审完成；你的任务只是补充学习反馈，不得重新评分，也不得改变已有结论。

请完成：
1. 对全文进行逐句检查，兼顾值得保留的亮点和真正需要修改的问题。
2. 检查错别字、用词、病句、标点、结构衔接与描写表达，但不要为了数量制造问题。
3. 为四个既有评分维度补充更具体的解释和原文依据。
4. 每个 quote 必须是学生原文中真实存在的连续片段。
5. 只返回一个 JSON 对象，不要输出 Markdown，不要返回新的总分或维度分数。

JSON 结构：
{
  "overall_analysis": "对核心总评的补充说明，不重复分数",
  "annotations": [
    {
      "category": "content|structure|language|expression|conventions",
      "kind": "improvement|strength",
      "issue_type": "typo|grammar|punctuation|wording|sentence|other",
      "severity": "low|medium|high",
      "quote": "原文真实片段",
      "start_offset": 0,
      "end_offset": 2,
      "comment": "这里怎么看或好在哪里",
      "suggestion": "可以怎么改或为什么值得保留"
    }
  ],
  "dimension_details": [
    {
      "dimension": "content_and_ideas|structure_and_coherence|language_and_expression|writing_conventions",
      "explanation": "这一维度当前判断的具体依据",
      "evidence": [{"quote": "原文真实片段", "rationale": "这段文字说明了什么"}]
    }
  ]
}
"""


def _chat_endpoint(base_url: str, explicit_url: str | None = None) -> str:
    if explicit_url:
        return explicit_url
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/chat/completions") else f"{normalized}/chat/completions"


def _configured_backends(preferred_keys: list[str]) -> list[DeepAnalysisBackend]:
    available: dict[str, DeepAnalysisBackend] = {}
    if settings.deepseek_api_key is not None:
        available["deepseek"] = DeepAnalysisBackend(
            "deepseek",
            _chat_endpoint(settings.deepseek_base_url, settings.deepseek_api_url),
            settings.deepseek_model,
            settings.deepseek_api_key,
        )
    if settings.qwen_api_key is not None:
        available["qwen"] = DeepAnalysisBackend(
            "qwen",
            _chat_endpoint(settings.qwen_base_url),
            settings.qwen_model,
            settings.qwen_api_key,
        )
    doubao_key = settings.ark_api_key or settings.doubao_api_key
    doubao_base_url = settings.ark_base_url if settings.ark_api_key is not None else settings.doubao_base_url
    if doubao_key is not None and doubao_base_url:
        available["doubao"] = DeepAnalysisBackend(
            "doubao",
            _chat_endpoint(doubao_base_url),
            settings.ark_deep_model if settings.ark_api_key is not None else settings.doubao_model,
            doubao_key,
        )
    ordered = list(dict.fromkeys([*preferred_keys, "deepseek", "qwen", "doubao"]))
    return [available[key] for key in ordered if key in available]


def _extract_content(response_data: dict[str, Any]) -> str:
    content = response_data["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValueError("empty response")
    return content


def _validated_output(essay_text: str, payload: str) -> DeepAnalysisOutput:
    output = DeepAnalysisOutput.model_validate(parse_json_object(payload))
    annotations = [item for item in output.annotations if item.quote in essay_text]
    details = [
        item.model_copy(
            update={"evidence": [evidence for evidence in item.evidence if evidence.quote in essay_text]}
        )
        for item in output.dimension_details
    ]
    if not annotations and not any(item.evidence for item in details):
        raise DeepAnalysisResponseFormatError("深度分析没有形成可定位的原文依据")
    return output.model_copy(update={"annotations": annotations, "dimension_details": details})


async def generate_deep_analysis(
    essay_text: str,
    quick_context: dict[str, object],
    preferred_provider_keys: list[str],
) -> DeepAnalysisProviderResult:
    backends = _configured_backends(preferred_provider_keys)
    if not backends:
        raise DeepAnalysisProviderUnavailableError("深度分析服务暂未配置")

    character_count = len(essay_text.replace(" ", "").replace("\n", ""))
    annotation_target = (
        "3–5" if character_count < 250 else
        "4–7" if character_count < 500 else
        "6–10" if character_count <= 800 else
        "8–12"
    )
    user_prompt = (
        f"作文长度约 {character_count} 字，建议形成 {annotation_target} 条有价值的旁批，以实际内容为准。\n"
        f"已经完成的核心评测：\n{json.dumps(quick_context, ensure_ascii=False)}\n\n"
        f"学生原文：\n{essay_text}"
    )
    last_error: DeepAnalysisGenerationError | None = None
    for backend in backends:
        payload = {
            "model": backend.model,
            "messages": [
                {"role": "system", "content": DEEP_ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": settings.deepseek_max_output_tokens,
            "temperature": 0.1,
            "stream": False,
        }
        if backend.key == "doubao":
            # This remains the Lite-only enrichment request. Extra reasoning
            # is unnecessary for its bounded JSON feedback contract.
            payload["thinking"] = {"type": "disabled"}
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
                last_error = DeepAnalysisGenerationError("深度分析请求暂未完成")
                continue
            response_data: dict[str, Any] = response.json()
            output = _validated_output(essay_text, _extract_content(response_data))
            response_model = response_data.get("model")
            return DeepAnalysisProviderResult(
                output=output,
                provider_key=backend.key,
                model_name=response_model if isinstance(response_model, str) else backend.model,
            )
        except httpx.TimeoutException:
            last_error = DeepAnalysisGenerationError("深度分析超时，请稍后重试")
        except httpx.HTTPError:
            last_error = DeepAnalysisGenerationError("深度分析服务暂时无法连接")
        except DeepAnalysisResponseFormatError as exc:
            last_error = exc
        except (KeyError, IndexError, TypeError, ValueError, ValidationError):
            last_error = DeepAnalysisResponseFormatError("深度分析结果格式不完整，请稍后重试")

    raise last_error or DeepAnalysisGenerationError("深度分析暂未完成，请稍后重试")
