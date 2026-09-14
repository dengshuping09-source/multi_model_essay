from __future__ import annotations

from dataclasses import dataclass
import logging
from time import perf_counter
from typing import Any

import httpx
from pydantic import SecretStr, ValidationError

from app.core.config import settings
from app.modules.reviews.contracts import parse_json_object
from app.schemas.training import (
    MicroExerciseType,
    MicroTrainingFeedback,
    MicroTrainingTask,
    TopicTrainingFeedback,
    TopicTrainingSubmission,
)


logger = logging.getLogger(__name__)


class TrainingGenerationError(RuntimeError):
    """Credential-safe error for a student-facing training request."""


class TrainingProviderUnavailableError(TrainingGenerationError):
    pass


class TrainingResponseFormatError(TrainingGenerationError):
    pass


@dataclass(frozen=True)
class TrainingBackend:
    key: str
    endpoint: str
    model: str
    api_key: SecretStr
    disable_thinking: bool = False


@dataclass(frozen=True)
class GeneratedTrainingFeedback:
    output: TopicTrainingFeedback
    provider_key: str
    model_name: str


@dataclass(frozen=True)
class GeneratedMicroTrainingFeedback:
    output: MicroTrainingFeedback
    provider_key: str
    model_name: str


SYSTEM_PROMPT = """你是一位耐心的中学语文老师，正在带学生完成写前的“审题与立意训练”。
这是训练，不是代写。你只能评价学生已经写出的审题、立意和提纲，指出遗漏并给启发，不能提供完整作文、标准答案或可直接抄写的成文段落。

请判断：
1. 学生是否抓住题目关键词、对象、范围、文体和其他限制；
2. 中心思想是否清楚、具体，并且回应题目；
3. 是否存在偏题风险；
4. 提纲是否围绕中心，若学生没有写提纲则自然提示，不把它视为严重错误；
5. 先肯定真实优点，再只指出最值得先修改的一点，并用问题或方向引导学生自己改。

只返回 JSON，不要 Markdown。所有面向学生的文字必须使用自然、简体中文，不使用模型、提示词、概率等技术说法。
JSON 结构固定为：
{
  "topic_understanding": "accurate|mostly_accurate|needs_revision",
  "idea_clarity": "clear|developing|unclear",
  "off_topic_risk": "low|medium|high",
  "structure_status": "focused|mostly_focused|needs_revision",
  "missing_constraints": ["遗漏的题目限制，最多4项"],
  "strengths": ["真实优点，最多2项"],
  "priority_issue": "现在最值得先修改的一点",
  "guidance": ["启发式修改方向，1到3项"],
  "next_step": "学生接下来可以自己完成的具体动作"
}
"""


MICRO_TRAINING_PROMPT = """你是一位耐心、简洁的中学语文老师，正在批改一项5到10分钟的写作微训练。
这不是正式作文评分，也不是代写。只判断学生是否完成本题的单一训练目标，肯定真实优点，并指出最值得改的一点。
不要生成完整作文，不要用100分制，不要扩展成与本题无关的长篇讲解。

只返回 JSON，不要 Markdown。所有面向学生的文字必须使用自然、简体中文。
JSON 结构固定为：
{
  "achievement": "excellent|met|needs_practice",
  "strengths": ["真实优点，最多2项"],
  "priority_issue": "最需要改的一点",
  "suggestions": ["具体、简短、可自己完成的修改建议，1到2项"],
  "recommend_retry": true,
  "next_step": "下一步行动"
}
"""


MICRO_TASKS: dict[MicroExerciseType, tuple[MicroTrainingTask, ...]] = {
    "opening": (
        MicroTrainingTask(
            task_id="opening-growth-01",
            exercise_type="opening",
            title="开头快速入题",
            goal="在开头交代具体情境，并自然点出题目方向。",
            prompt="请以“那一刻，我没有退缩”为题写一个作文开头。",
            instruction="写80～120字。不要先讲大道理，从一个具体时刻或动作进入。",
            input_hint="从当时在哪里、发生了什么、你准备怎么做写起……",
            suggested_minutes=7,
            min_characters=60,
            max_characters=160,
        ),
    ),
    "outline_structure": (
        MicroTrainingTask(
            task_id="outline-kindness-01",
            exercise_type="outline_structure",
            title="三步搭好文章结构",
            goal="让开头、主体和结尾都围绕同一个中心。",
            prompt="题目：藏在细节里的温暖",
            instruction="用三到五行写出开头、主要事件和结尾，并在每一部分注明它怎样表现“温暖”。",
            input_hint="开头：……\n主体：……\n结尾：……",
            suggested_minutes=6,
            min_characters=40,
            max_characters=260,
        ),
    ),
    "evidence_development": (
        MicroTrainingTask(
            task_id="evidence-persistence-01",
            exercise_type="evidence_development",
            title="把材料和观点连起来",
            goal="写清事实为什么能够证明观点，而不是只讲一个故事。",
            prompt="观点：坚持并不是机械重复，而是在困难中不断调整方法。",
            context="材料：小林连续三次参加机器人比赛都没有获奖。他每次赛后记录故障原因，修改程序和结构，第四次终于完成了稳定运行。",
            instruction="用80～150字分析材料与观点之间的关系，至少写清一次“为什么”。",
            input_hint="这件事能够说明……因为……",
            suggested_minutes=8,
            min_characters=60,
            max_characters=200,
        ),
    ),
    "paragraph_transition": (
        MicroTrainingTask(
            task_id="transition-library-01",
            exercise_type="paragraph_transition",
            title="让两段话自然接上",
            goal="补出承接上文、引出下文的过渡。",
            prompt="请为下面两段之间补写一段过渡。",
            context="上文：我一直觉得社区里的旧图书角又小又乱，很少有人愿意停留。\n\n下文：整理后的第一个周末，我看见几个孩子坐在新贴好的分类标签旁认真读书。",
            instruction="写40～80字，既说明“我”为什么开始整理，也自然引出整理后的变化。",
            input_hint="直到有一天……于是我决定……",
            suggested_minutes=5,
            min_characters=30,
            max_characters=110,
        ),
    ),
    "sentence_revision": (
        MicroTrainingTask(
            task_id="sentence-rain-01",
            exercise_type="sentence_revision",
            title="把句子改得具体流畅",
            goal="减少重复和空泛表达，让动作与感受更清楚。",
            prompt="修改下面的句子：我非常紧张地紧紧握住手里的演讲稿，心里感到十分紧张，但是我还是很勇敢地走上了讲台。",
            instruction="保留原意，改写成一到两句话，并简要说明你主要改了什么。",
            input_hint="修改：……\n我主要调整了：……",
            suggested_minutes=5,
            min_characters=30,
            max_characters=180,
        ),
    ),
    "ending": (
        MicroTrainingTask(
            task_id="ending-bicycle-01",
            exercise_type="ending",
            title="结尾自然点题",
            goal="回应前文变化，让中心落在具体感受上。",
            prompt="题目：这一次，我学会了坚持",
            context="前文写“我”多次摔倒后终于学会骑自行车，最后一次独自骑过了小区的长坡。",
            instruction="写60～100字结尾。不要喊口号，要回应长坡或骑车的具体经历。",
            input_hint="风从耳边吹过……",
            suggested_minutes=6,
            min_characters=45,
            max_characters=140,
        ),
    ),
}


def get_micro_training_task(exercise_type: MicroExerciseType, completed_count: int = 0) -> MicroTrainingTask:
    tasks = MICRO_TASKS[exercise_type]
    return tasks[completed_count % len(tasks)]


def get_micro_training_task_by_id(task_id: str) -> MicroTrainingTask | None:
    return next(
        (task for tasks in MICRO_TASKS.values() for task in tasks if task.task_id == task_id),
        None,
    )


def _chat_endpoint(base_url: str, explicit_url: str | None = None) -> str:
    if explicit_url:
        return explicit_url
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/chat/completions") else f"{normalized}/chat/completions"


def _configured_backends() -> list[TrainingBackend]:
    """Prefer a fast configured model and fall back only after a real failure."""

    backends: list[TrainingBackend] = []
    if settings.qwen_api_key is not None:
        backends.append(
            TrainingBackend(
                "qwen", _chat_endpoint(settings.qwen_base_url), settings.qwen_model, settings.qwen_api_key
            )
        )
    if settings.deepseek_api_key is not None:
        backends.append(
            TrainingBackend(
                "deepseek",
                _chat_endpoint(settings.deepseek_base_url, settings.deepseek_api_url),
                settings.deepseek_model,
                settings.deepseek_api_key,
            )
        )
    doubao_key = settings.ark_api_key or settings.doubao_api_key
    doubao_base_url = settings.ark_base_url if settings.ark_api_key is not None else settings.doubao_base_url
    if doubao_key is not None and doubao_base_url:
        backends.append(
            TrainingBackend(
                "doubao",
                _chat_endpoint(doubao_base_url),
                settings.ark_quick_model if settings.ark_api_key is not None else settings.doubao_model,
                doubao_key,
                disable_thinking=settings.ark_api_key is not None,
            )
        )
    return backends


def _extract_content(payload: dict[str, Any]) -> str:
    content = payload["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValueError("empty response")
    return content.strip()


def _looks_english_dominant(value: str) -> bool:
    chinese = sum("\u3400" <= character <= "\u9fff" for character in value)
    latin = sum(character.isascii() and character.isalpha() for character in value)
    return latin >= 8 and chinese * 2 < latin


def _validate_feedback(output: TopicTrainingFeedback) -> TopicTrainingFeedback:
    visible_values = [
        *output.missing_constraints,
        *output.strengths,
        output.priority_issue,
        *output.guidance,
        output.next_step,
    ]
    if any(_looks_english_dominant(value) for value in visible_values):
        raise TrainingResponseFormatError("训练反馈没有返回中文说明")
    return output


async def _request_feedback(
    backend: TrainingBackend, submission: TopicTrainingSubmission
) -> GeneratedTrainingFeedback:
    user_prompt = (
        f"作文题目或材料：\n{submission.topic_prompt}\n\n"
        f"学生理解的关键词和核心要求：\n{submission.requirement_notes}\n\n"
        f"学生准备表达的中心：\n{submission.central_idea}\n\n"
        f"学生的思路或提纲：\n{submission.outline or '暂未填写'}"
    )
    request_payload: dict[str, Any] = {
        "model": backend.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 900,
        "temperature": 0.2,
        "stream": False,
    }
    if backend.disable_thinking:
        request_payload["thinking"] = {"type": "disabled"}

    started_at = perf_counter()
    logger.info("topic_training_started provider=%s model=%s", backend.key, backend.model)
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.model_review_timeout_seconds, connect=10.0)
        ) as client:
            response = await client.post(
                backend.endpoint,
                headers={"Authorization": f"Bearer {backend.api_key.get_secret_value()}"},
                json=request_payload,
            )
        if response.is_error:
            raise TrainingGenerationError("训练反馈服务暂时没有完成请求")
        output = _validate_feedback(
            TopicTrainingFeedback.model_validate(parse_json_object(_extract_content(response.json())))
        )
    except httpx.TimeoutException as exc:
        raise TrainingGenerationError("训练反馈生成超时，请稍后重试") from exc
    except httpx.HTTPError as exc:
        raise TrainingGenerationError("训练反馈服务暂时无法连接") from exc
    except TrainingGenerationError:
        raise
    except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
        raise TrainingResponseFormatError("训练反馈暂时不完整，请稍后重试") from exc
    logger.info(
        "topic_training_completed provider=%s model=%s elapsed_ms=%d",
        backend.key,
        backend.model,
        round((perf_counter() - started_at) * 1000),
    )
    return GeneratedTrainingFeedback(output, backend.key, backend.model)


async def generate_topic_training_feedback(
    submission: TopicTrainingSubmission,
) -> GeneratedTrainingFeedback:
    backends = _configured_backends()
    if not backends:
        raise TrainingProviderUnavailableError("训练反馈服务暂未配置")
    last_error: TrainingGenerationError | None = None
    for backend in backends:
        try:
            return await _request_feedback(backend, submission)
        except TrainingGenerationError as exc:
            last_error = exc
            logger.warning(
                "topic_training_provider_failed provider=%s error_type=%s",
                backend.key,
                type(exc).__name__,
            )
    raise last_error or TrainingGenerationError("训练反馈暂时无法生成，请稍后重试")


async def _request_micro_feedback(
    backend: TrainingBackend,
    task: MicroTrainingTask,
    response_text: str,
) -> GeneratedMicroTrainingFeedback:
    user_prompt = (
        f"训练名称：{task.title}\n"
        f"训练目标：{task.goal}\n"
        f"题目：{task.prompt}\n"
        f"补充材料：{task.context or '无'}\n"
        f"作答要求：{task.instruction}\n\n"
        f"学生作答：\n{response_text}"
    )
    request_payload: dict[str, Any] = {
        "model": backend.model,
        "messages": [
            {"role": "system", "content": MICRO_TRAINING_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 600,
        "temperature": 0.2,
        "stream": False,
    }
    if backend.disable_thinking:
        request_payload["thinking"] = {"type": "disabled"}

    started_at = perf_counter()
    logger.info("micro_training_started provider=%s model=%s task_id=%s", backend.key, backend.model, task.task_id)
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.model_review_timeout_seconds, connect=10.0)
        ) as client:
            response = await client.post(
                backend.endpoint,
                headers={"Authorization": f"Bearer {backend.api_key.get_secret_value()}"},
                json=request_payload,
            )
        if response.is_error:
            raise TrainingGenerationError("专项训练反馈暂时没有完成请求")
        output = MicroTrainingFeedback.model_validate(
            parse_json_object(_extract_content(response.json()))
        )
        visible_values = [
            *output.strengths,
            output.priority_issue,
            *output.suggestions,
            output.next_step,
        ]
        if any(_looks_english_dominant(value) for value in visible_values):
            raise TrainingResponseFormatError("专项训练反馈没有返回中文说明")
    except httpx.TimeoutException as exc:
        raise TrainingGenerationError("专项训练反馈生成超时，请稍后重试") from exc
    except httpx.HTTPError as exc:
        raise TrainingGenerationError("专项训练反馈服务暂时无法连接") from exc
    except TrainingGenerationError:
        raise
    except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
        raise TrainingResponseFormatError("专项训练反馈暂时不完整，请稍后重试") from exc
    logger.info(
        "micro_training_completed provider=%s model=%s task_id=%s elapsed_ms=%d",
        backend.key,
        backend.model,
        task.task_id,
        round((perf_counter() - started_at) * 1000),
    )
    return GeneratedMicroTrainingFeedback(output, backend.key, backend.model)


async def generate_micro_training_feedback(
    task: MicroTrainingTask,
    response_text: str,
) -> GeneratedMicroTrainingFeedback:
    backends = _configured_backends()
    if not backends:
        raise TrainingProviderUnavailableError("专项训练反馈服务暂未配置")
    last_error: TrainingGenerationError | None = None
    for backend in backends:
        try:
            return await _request_micro_feedback(backend, task, response_text)
        except TrainingGenerationError as exc:
            last_error = exc
            logger.warning(
                "micro_training_provider_failed provider=%s task_id=%s error_type=%s",
                backend.key,
                task.task_id,
                type(exc).__name__,
            )
    raise last_error or TrainingGenerationError("专项训练反馈暂时无法生成，请稍后重试")
