from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from app.db.models import Essay, FinalEvaluation, ModelReview, ReviewRecheck, ReviewStatus


PROVIDER_LABELS = {"deepseek": "DeepSeek", "qwen": "Qwen", "doubao": "豆包"}
REVIEW_STATUS_LABELS = {
    "pending": "等待中",
    "running": "进行中",
    "completed": "已完成",
    "failed": "未完成",
}
RECHECK_STATUS_LABELS = {
    "pending": "等待复核",
    "running": "复核中",
    "completed": "已完成",
    "skipped": "无需复核",
    "failed": "未完成",
}
DIMENSION_LABELS = {
    "content_and_ideas": "内容与立意",
    "structure_and_coherence": "结构与连贯",
    "language_and_expression": "语言与表达",
    "writing_conventions": "书写规范",
}
CONSISTENCY_LABELS = {
    "high": "主要判断一致",
    "medium": "部分判断存在差异",
    "low": "存在较明显分歧",
}


def _paragraph(value: object, style: ParagraphStyle) -> Paragraph:
    text = escape(str(value or "--")).replace("\n", "<br/>")
    # Keep user/model text escaped, while restoring the small fixed markup subset
    # used by this module for document hierarchy.
    for escaped_tag, safe_tag in {
        "&lt;b&gt;": "<b>",
        "&lt;/b&gt;": "</b>",
        "&lt;br/&gt;": "<br/>",
        "&lt;font size=9&gt;": '<font size="9">',
        "&lt;/font&gt;": "</font>",
    }.items():
        text = text.replace(escaped_tag, safe_tag)
    return Paragraph(text, style)


def _dimensions(final: FinalEvaluation) -> list[dict[str, Any]]:
    return [item for item in (final.dimension_scores or []) if isinstance(item, dict)]


def _report_payload(final: FinalEvaluation, key: str) -> dict[str, Any]:
    config = final.aggregation_config if isinstance(final.aggregation_config, dict) else {}
    value = config.get(key)
    return value if isinstance(value, dict) else {}


def _dict_items(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _average_spread(final: FinalEvaluation | None) -> float | None:
    if final is None:
        return None
    spreads = [
        float(item["spread"])
        for item in _dimensions(final)
        if isinstance(item.get("spread"), (int, float))
    ]
    return round(sum(spreads) / len(spreads), 2) if spreads else None


def _dispute_text(dispute: object) -> str:
    if not isinstance(dispute, dict):
        return str(dispute)
    if dispute.get("type") == "dimension_disagreement":
        dimension = DIMENSION_LABELS.get(str(dispute.get("dimension")), str(dispute.get("dimension")))
        return f"{dimension}分歧 {dispute.get('spread', '--')} 分"
    if dispute.get("type") == "outlier_score":
        providers = "、".join(str(item) for item in dispute.get("providers", []))
        return f"异常总分：{providers or '某模型'} 与中位数偏离较大"
    return "检测到需要进一步确认的评分差异"


def _review_summary(review: ModelReview) -> str:
    if review.status is ReviewStatus.COMPLETED and review.summary:
        return review.summary
    return "该评审视角未形成有效结果，综合报告未采用这一路判断。"


def build_report_pdf(
    essay: Essay,
    final: FinalEvaluation,
    reviews: list[ModelReview],
    rechecks: list[tuple[ReviewRecheck, FinalEvaluation | None, FinalEvaluation | None]],
) -> bytes:
    """Build a static PDF from persisted report data only; no model is invoked here."""
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"文衡作文评测报告 - {essay.title or '未命名作文'}",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("ReportTitle", parent=styles["Title"], fontName="STSong-Light", fontSize=21, leading=28, textColor=colors.HexColor("#1f4e58"), wordWrap="CJK")
    heading = ParagraphStyle("ReportHeading", parent=styles["Heading2"], fontName="STSong-Light", fontSize=14, leading=20, textColor=colors.HexColor("#1f4e58"), spaceBefore=12, spaceAfter=7, wordWrap="CJK")
    body = ParagraphStyle("ReportBody", parent=styles["BodyText"], fontName="STSong-Light", fontSize=9.4, leading=15, textColor=colors.HexColor("#263c43"), wordWrap="CJK")
    muted = ParagraphStyle("ReportMuted", parent=body, fontSize=8.4, leading=13, textColor=colors.HexColor("#60737a"))
    score_style = ParagraphStyle("ReportScore", parent=styles["Title"], fontName="STSong-Light", fontSize=28, leading=34, alignment=TA_CENTER, textColor=colors.HexColor("#176f67"))
    story: list[object] = []

    story.extend([
        _paragraph("文衡作文评测报告", title),
        _paragraph(essay.title or "未命名作文", heading),
        _paragraph(
            f"年级：{essay.grade_level or '未填写'}　文体：{essay.genre or '未填写'}　满分：{essay.full_score}",
            muted,
        ),
        Spacer(1, 6 * mm),
    ])

    confidence = float(final.confidence or 0) * 100
    overview = Table(
        [[
            _paragraph(f"{float(final.overall_score) if final.overall_score is not None else '--'}<br/><font size=9>综合评分 / {essay.full_score}</font>", score_style),
            _paragraph(
                f"<b>可信度 {confidence:.0f}%</b><br/>"
                f"评测一致性：{CONSISTENCY_LABELS.get(str(final.consistency), '暂缺足够信息')}<br/>"
                f"{final.summary or '暂无综合说明'}",
                body,
            ),
        ]],
        colWidths=[50 * mm, 125 * mm],
    )
    overview.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#e7f4f1")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#bad8d1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d7e8e3")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.extend([overview, Spacer(1, 4 * mm), _paragraph("评分维度与模型差异", heading)])

    feedback = _report_payload(final, "learning_feedback")
    priority_issues = _dict_items(feedback.get("priority_issues"))
    strengths = _dict_items(feedback.get("strengths"))
    if priority_issues:
        story.append(_paragraph("本次最值得先改", heading))
        for item in priority_issues[:3]:
            suggestion = item.get("suggestion")
            if suggestion:
                story.append(_paragraph(f"- {suggestion}", body))
    if strengths:
        story.append(_paragraph("做得好的地方", heading))
        for item in strengths[:3]:
            comment = item.get("comment")
            if comment:
                story.append(_paragraph(f"- {comment}", body))

    dimension_rows: list[list[Paragraph]] = [[
        _paragraph("维度", body), _paragraph("综合", body), _paragraph("分歧", body), _paragraph("模型评分", body),
    ]]
    for item in _dimensions(final):
        provider_scores = item.get("provider_scores") if isinstance(item.get("provider_scores"), dict) else {}
        score_text = "；".join(
            f"{PROVIDER_LABELS.get(str(key), str(key))} {value}" for key, value in provider_scores.items()
        ) or "--"
        dimension_rows.append([
            _paragraph(DIMENSION_LABELS.get(str(item.get("dimension")), str(item.get("dimension", "--"))), body),
            _paragraph(f"{item.get('score', '--')} / {item.get('max_score', 25)}", body),
            _paragraph(f"{item.get('spread', '--')} 分", body),
            _paragraph(score_text, body),
        ])
    dimension_table = Table(dimension_rows, colWidths=[36 * mm, 27 * mm, 25 * mm, 87 * mm], repeatRows=1)
    dimension_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#245e70")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c9d8dc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([dimension_table, _paragraph("可信度说明", heading)])
    factors = (final.aggregation_config or {}).get("confidence_factors", {}) if isinstance(final.aggregation_config, dict) else {}
    for factor in factors.get("explanation", []) if isinstance(factors, dict) else []:
        if isinstance(factor, dict):
            story.append(_paragraph(f"<b>{factor.get('label', '因素')}</b>：{factor.get('detail', '')}", body))
    story.append(_paragraph("可信度由模型完成度与各维度一致性共同计算；它不是对作文质量的第二次评分。", muted))

    if final.disputes:
        story.append(_paragraph("争议与异常结果", heading))
        for dispute in final.disputes:
            story.append(_paragraph(f"- {_dispute_text(dispute)}", body))

    story.append(_paragraph("独立模型意见", heading))
    for review in reviews:
        output = review.raw_response.get("output") if isinstance(review.raw_response, dict) else None
        summary = _review_summary(review)
        story.append(_paragraph(
            f"<b>{PROVIDER_LABELS.get(review.model_provider, review.model_provider)}</b>　"
            f"状态：{REVIEW_STATUS_LABELS.get(review.status.value, '状态未知')}　"
            f"总分：{float(review.overall_score) if review.overall_score is not None else '--'}",
            body,
        ))
        story.append(_paragraph(summary, body))
        if isinstance(output, dict):
            suggestions = output.get("improvement_suggestions")
            if isinstance(suggestions, list) and suggestions:
                first = suggestions[0]
                if isinstance(first, dict):
                    story.append(_paragraph(f"建议：{first.get('suggestion', '--')}", muted))
        story.append(Spacer(1, 3 * mm))

    if rechecks:
        story.append(_paragraph("交叉复核记录", heading))
        for recheck, baseline, resolved in rechecks:
            baseline_score = float(baseline.overall_score) if baseline and baseline.overall_score is not None else "--"
            resolved_score = float(resolved.overall_score) if resolved and resolved.overall_score is not None else "--"
            baseline_spread = _average_spread(baseline)
            resolved_spread = _average_spread(resolved)
            story.append(_paragraph(
                f"<b>{RECHECK_STATUS_LABELS.get(recheck.status.value, '状态未知')}</b>：{recheck.trigger_reason}<br/>"
                f"复核前总分 {baseline_score}，平均分歧 {baseline_spread if baseline_spread is not None else '--'}；"
                f"复核后总分 {resolved_score}，平均分歧 {resolved_spread if resolved_spread is not None else '--'}。<br/>"
                f"{recheck.result_summary or '暂无复核说明'}",
                body,
            ))

    annotations = [annotation for review in reviews for annotation in review.annotations][:12]
    if annotations:
        story.append(_paragraph("原文证据与修改建议", heading))
        for annotation in annotations:
            story.append(_paragraph(
                f"<b>“{annotation.evidence_text or '原文片段'}”</b>：{annotation.comment}"
                f"{' 建议：' + annotation.suggestion if annotation.suggestion else ''}",
                body,
            ))

    deep_analysis = _report_payload(final, "deep_analysis")
    deep_annotations = _dict_items(deep_analysis.get("annotations"))
    if deep_analysis.get("status") == "completed" and deep_annotations:
        story.append(_paragraph("深入反馈", heading))
        for annotation in deep_annotations[:16]:
            quote = annotation.get("evidence_text") or annotation.get("quote") or "原文片段"
            comment = annotation.get("comment") or ""
            suggestion = annotation.get("suggestion") or ""
            story.append(_paragraph(
                f"<b>“{quote}”</b>：{comment}{' 建议：' + str(suggestion) if suggestion else ''}",
                body,
            ))

    if essay.original_text:
        story.append(_paragraph("本次评测原文", heading))
        story.append(_paragraph(essay.original_text, body))

    story.append(Spacer(1, 7 * mm))
    story.append(_paragraph(
        "本报告根据已确认的作文文字和评测结果生成。导出不会重新识别图片或重新评测。",
        muted,
    ))
    document.build(story)
    return buffer.getvalue()
