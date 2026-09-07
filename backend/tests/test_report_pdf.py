from types import SimpleNamespace

from app.db.models import ReviewStatus
from app.modules.reports.pdf import build_report_pdf


def test_report_pdf_contains_a_valid_pdf_document(tmp_path) -> None:
    essay = SimpleNamespace(
        title="雨后那盏灯",
        grade_level="初二",
        genre="记叙文",
        full_score=100,
    )
    final = SimpleNamespace(
        overall_score=84,
        confidence=0.72,
        consistency="medium",
        summary="Two model results were available for aggregation.",
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
        summary="The narrative has a clear scene.",
        raw_response={"output": {"improvement_suggestions": [{"suggestion": "Add one sensory detail."}]}},
        annotations=[],
    )

    content = build_report_pdf(essay, final, [review], [])
    output_path = tmp_path / "report.pdf"
    output_path.write_bytes(content)

    assert content.startswith(b"%PDF")
    assert output_path.stat().st_size > 1_000
