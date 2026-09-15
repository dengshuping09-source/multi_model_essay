import asyncio

import pytest

from app.modules.reviews.contracts import EssayPolishOutput, PolishChange
from app.modules.reviews import polish
from app.modules.reviews.polish import PolishGenerationError, PolishResponseFormatError, validate_polish


ORIGINAL = "雨停了，我走进巷子。地上的水很亮，我慢慢走回家。"


def test_validate_polish_accepts_bounded_explainable_changes() -> None:
    output = EssayPolishOutput(
        polished_text="雨停了，我走进安静的巷子。地上的积水闪着微光，我慢慢走回家。",
        overview="补充了少量环境细节，让画面更清楚。",
        changes=[
            PolishChange(
                original="巷子",
                revised="安静的巷子",
                reason="增加环境特点，但不改变原意。",
                category="detail",
            ),
            PolishChange(
                original="水很亮",
                revised="积水闪着微光",
                reason="表达更具体，画面更容易想象。",
                category="wording",
            ),
        ],
    )

    assert validate_polish(ORIGINAL, output).polished_text == output.polished_text


def test_validate_polish_rejects_a_complete_rewrite() -> None:
    output = EssayPolishOutput(
        polished_text="这是另一篇与原文人物、情节和主题完全无关的作文。" * 3,
        overview="完全改写。",
        changes=[
            PolishChange(
                original="雨停了",
                revised="这是另一篇",
                reason="测试。",
                category="sentence",
            )
        ],
    )

    with pytest.raises(PolishResponseFormatError):
        validate_polish(ORIGINAL, output)


def test_validate_polish_rejects_untraceable_change() -> None:
    output = EssayPolishOutput(
        polished_text="雨停了，我走进巷子。地上的水很明亮，我慢慢走回家。",
        overview="改善表达。",
        changes=[
            PolishChange(
                original="原文里不存在的句子",
                revised="水很明亮",
                reason="测试。",
                category="wording",
            )
        ],
    )

    with pytest.raises(PolishResponseFormatError):
        validate_polish(ORIGINAL, output)


def test_validate_polish_discards_a_change_that_removes_a_paragraph() -> None:
    original = "第一段保留中心观点，说明自己的经历。\n第二段保留具体事例，说明为什么要坚持。\n第三段保留结尾，回应题目。"
    output = EssayPolishOutput(
        polished_text="第一段保留中心观点，说明自己的经历。\n第二段。\n第三段保留结尾，回应题目。",
        overview="大幅压缩中间内容。",
        changes=[
            PolishChange(
                original="第二段保留具体事例，说明为什么要坚持。",
                revised="第二段。",
                reason="测试。",
                category="structure",
            )
        ],
    )

    with pytest.raises(PolishResponseFormatError):
        validate_polish(original, output)


def test_validate_polish_keeps_traceable_changes_and_discards_an_imprecise_quote() -> None:
    output = EssayPolishOutput(
        polished_text="雨停了，我走进安静的巷子。地上的积水闪着微光，我慢慢走回家。",
        overview="保留原意，改善两处表达。",
        changes=[
            PolishChange(
                original="巷子",
                revised="安静的巷子",
                reason="补充环境特点。",
                category="detail",
            ),
            PolishChange(
                original="地面上的水很亮",
                revised="积水闪着微光",
                reason="表达更具体。",
                category="wording",
            ),
        ],
    )

    validated = validate_polish(ORIGINAL, output)

    assert validated.polished_text == "雨停了，我走进安静的巷子。地上的水很亮，我慢慢走回家。"
    assert [change.original for change in validated.changes] == ["巷子"]


def test_validate_polish_accepts_no_change_when_original_is_already_clear() -> None:
    output = EssayPolishOutput(
        polished_text=ORIGINAL,
        overview="原文表达已经清楚，建议保留。",
        changes=[],
    )

    validated = validate_polish(ORIGINAL, output)

    assert validated.polished_text == ORIGINAL
    assert validated.changes == []


def test_validate_polish_recovers_bounded_changes_when_provider_omits_them() -> None:
    output = EssayPolishOutput(
        polished_text="雨停了，我走进安静的巷子。地上的水很亮，我慢慢走回家。",
        overview="补充了环境特点。",
        changes=[],
    )

    validated = validate_polish(ORIGINAL, output)

    assert validated.polished_text == "雨停了，我走进安静的巷子。地上的水很亮，我慢慢走回家。"
    assert len(validated.changes) == 1
    assert "安静的巷子" in validated.changes[0].revised


def test_validate_polish_rejects_english_student_copy_for_chinese_essay() -> None:
    output = EssayPolishOutput(
        polished_text="The rain stopped and I walked into the alley.",
        overview="Improve the wording and make the scene clearer.",
        changes=[
            PolishChange(
                original="雨停了",
                revised="The rain stopped",
                reason="This makes the opening clearer.",
                category="wording",
            )
        ],
    )

    with pytest.raises(PolishResponseFormatError):
        validate_polish(ORIGINAL, output)


def test_generate_polish_uses_first_success_without_waiting_for_failed_backend(monkeypatch) -> None:
    successful = EssayPolishOutput(
        polished_text="雨停了，我走进安静的巷子。地上的水很亮，我慢慢走回家。",
        overview="补充了环境特点。",
        changes=[
            PolishChange(
                original="巷子",
                revised="安静的巷子",
                reason="画面更清楚。",
                category="detail",
            )
        ],
    )
    backends = [object(), object()]

    async def fake_request(backend, essay_text, user_prompt):
        assert essay_text == ORIGINAL
        assert "学生原文" in user_prompt
        if backend is backends[0]:
            await asyncio.sleep(0.01)
            raise PolishGenerationError("暂时不可用")
        await asyncio.sleep(0.02)
        return successful

    monkeypatch.setattr(polish, "_configured_backends", lambda: backends)
    monkeypatch.setattr(polish, "_request_polish", fake_request)

    assert asyncio.run(polish.generate_polish(ORIGINAL, "总评", ["补充细节"])) == successful
