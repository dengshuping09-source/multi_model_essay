from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


SCORING_STANDARD_VERSION = "cn-essay-v2"
PROMPT_VERSION = "essay-review-v5-quick-focused-feedback"


@dataclass(frozen=True)
class EssayReviewContext:
    grade_level: str | None
    genre: str | None
    writing_prompt: str | None
    full_score: int
    review_mode: Literal["quick"] = "quick"


def scoring_instruction(context: EssayReviewContext, essay_text: str = "") -> str:
    char_count = len(essay_text.strip())
    details = [
        "使用统一的中文作文评分标准 cn-essay-v2。",
        "为了便于多个独立评审比较，分数统一按 100 分计算：四个必填维度各 0–25 分。",
        "结合提供的学习情境评阅作文。题目满分只用于理解任务，不得改变统一的 100 分评分规则。",
        f"年级：{context.grade_level or '未提供'}。",
        f"文体：{context.genre or '未提供'}。",
        f"写作题目或要求：{context.writing_prompt or '未提供'}。",
        f"作业原始满分：{context.full_score} 分。",
        "未提供的信息不得扣分。引用只能使用学生原文中连续、完全一致的片段；建议要具体、适合该年级学生执行。",
        f"作文约 {char_count} 个字符。",
        "这是快速评测阶段：总评保持简短；每个维度最多保留一处原文依据；给出 1–3 条最高优先级修改建议。",
        "同时只挑选 1–2 条最重要、能够精确回到原文的反馈。每条都必须填写原文片段、判断和可执行建议；最多一条可以是值得保留的亮点。",
        "不要进行全文逐句扫描、完整错别字/病句/标点检查、全文润色、长示例或技术说明；这些只在学生主动开始深度评测后补充。",
        "如果学生原文主要是中文，除原文引用和固定 JSON 枚举值外，所有面向学生的文字必须使用自然、简体中文，不得输出英文句子。",
    ]
    return "\n".join(details)
