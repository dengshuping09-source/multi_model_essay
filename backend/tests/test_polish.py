import pytest

from app.modules.reviews.contracts import EssayPolishOutput, PolishChange
from app.modules.reviews.polish import PolishResponseFormatError, validate_polish


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
