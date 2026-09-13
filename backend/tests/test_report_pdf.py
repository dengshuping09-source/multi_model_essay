from types import SimpleNamespace

from app.db.models import ReviewStatus
from app.modules.reports.pdf import build_report_pdf


def test_report_pdf_contains_a_valid_pdf_document(tmp_path) -> None:
    essay = SimpleNamespace(
        title="雨后那盏灯",
        grade_level="初二",
        genre="记叙文",
        full_score=100,
        original_text=("雨停以后，我沿着湿漉漉的小路慢慢走回家。路灯映在水面上，像一颗安静的星。" * 90),
    )
    final = SimpleNamespace(
        overall_score=84,
        confidence=0.72,
        consistency="medium",
        summary="文章主题清楚，叙事完整；如果补充人物动作，画面会更具体。",
        dimension_scores=[
            {
                "dimension": "content_and_ideas",
                "score": 21,
                "max_score": 25,
                "spread": 4,
                "provider_scores": {"deepseek": 22, "qwen": 18},
            }
        ],
        disputes=[{"type": "dimension_disagreement", "dimension": "content_and_ideas", "spread": 9}],
        aggregation_config={
            "learning_feedback": {
                "priority_issues": [{"suggestion": "补充人物动作和环境细节。"}],
                "strengths": [{"comment": "结尾能够回扣题目。"}],
            },
            "confidence_factors": {
                "explanation": [
                    {"label": "模型完成度", "detail": "2/3 个模型返回了结果。"}
                ]
            }
        },
    )
    review = SimpleNamespace(
        model_provider="deepseek",
        status=ReviewStatus.COMPLETED,
        overall_score=86,
        summary="叙事场景清楚，主题表达自然。",
        raw_response={"output": {"improvement_suggestions": [{"suggestion": "补充一处感官细节。"}]}},
        annotations=[],
    )

    content = build_report_pdf(essay, final, [review], [])
    output_path = tmp_path / "report.pdf"
    output_path.write_bytes(content)

    assert content.startswith(b"%PDF")
    assert output_path.stat().st_size > 1_000
    assert content.count(b"/Type /Page") >= 3
    assert b"STSong-Light" in content
