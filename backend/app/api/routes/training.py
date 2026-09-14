from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser
from app.db.models import Essay, EssayStatus, FinalEvaluation, ReviewStatus, WritingTrainingSession
from app.db.session import get_db_session
from app.modules.essays.growth import build_growth_summary
from app.modules.training.service import (
    TrainingGenerationError,
    generate_micro_training_feedback,
    generate_topic_training_feedback,
    get_micro_training_task,
    get_micro_training_task_by_id,
)
from app.schemas.training import (
    MicroExerciseType,
    MicroTrainingFeedback,
    MicroTrainingResult,
    MicroTrainingSubmission,
    MicroTrainingTask,
    TopicTrainingFeedback,
    TopicTrainingHistoryResponse,
    TopicTrainingSessionResponse,
    TopicTrainingSubmission,
    TrainingRecommendation,
    TrainingRecommendationResponse,
)


router = APIRouter(tags=["writing-training"])


MICRO_TRAINING_TITLES: dict[MicroExerciseType, str] = {
    "opening": "开头快速入题",
    "outline_structure": "结构与提纲训练",
    "evidence_development": "论据展开训练",
    "paragraph_transition": "段落衔接训练",
    "sentence_revision": "句式修改训练",
    "ending": "结尾与点题训练",
}


def _latest_completed_final(essay: Essay) -> FinalEvaluation | None:
    completed = [
        item for item in essay.final_evaluations if item.status == ReviewStatus.COMPLETED
    ]
    return max(completed, key=lambda item: item.version, default=None)


def _recommended_exercise(issue: dict[str, object]) -> MicroExerciseType:
    label = str(issue.get("label") or "")
    statement = str(issue.get("latest_statement") or "")
    category = str(issue.get("category") or "").lower()
    issue_type = str(issue.get("issue_type") or "").lower()
    combined = f"{label} {statement}"
    if "开头" in combined or "入题" in combined:
        return "opening"
    if "结尾" in combined or "点题" in combined:
        return "ending"
    if "衔接" in combined or "过渡" in combined or "连贯" in combined:
        return "paragraph_transition"
    if issue_type in {"typo", "punctuation", "grammar", "wording", "sentence"}:
        return "sentence_revision"
    if any(keyword in combined for keyword in ("论据", "展开", "细节", "具体", "充实")):
        return "evidence_development"
    if category == "structure" or any(keyword in combined for keyword in ("结构", "中心", "立意")):
        return "outline_structure"
    return "sentence_revision" if category in {"language", "expression", "conventions"} else "outline_structure"


def _general_recommendations() -> list[TrainingRecommendation]:
    return [
        TrainingRecommendation(
            exercise_type="opening",
            title=MICRO_TRAINING_TITLES["opening"],
            reason="适合先练习如何快速进入具体内容。完成正式评测后，这里会根据真实反馈调整推荐。",
            personalized=False,
            evidence_work_count=0,
        ),
        TrainingRecommendation(
            exercise_type="outline_structure",
            title=MICRO_TRAINING_TITLES["outline_structure"],
            reason="适合建立基础的文章结构意识，不代表这是你的个人弱项。",
            personalized=False,
            evidence_work_count=0,
        ),
        TrainingRecommendation(
            exercise_type="sentence_revision",
            title=MICRO_TRAINING_TITLES["sentence_revision"],
            reason="适合用短句练习清楚、流畅的表达，不代表这是你的个人弱项。",
            personalized=False,
            evidence_work_count=0,
        ),
    ]


def _response(record: WritingTrainingSession) -> TopicTrainingSessionResponse:
    return TopicTrainingSessionResponse(
        id=record.id,
        training_type=record.training_type,
        topic_prompt=record.topic_prompt,
        requirement_notes=record.requirement_notes,
        central_idea=record.central_idea,
        outline=record.outline,
        status=record.status,
        feedback=(
            TopicTrainingFeedback.model_validate(record.feedback)
            if isinstance(record.feedback, dict)
            else None
        ),
        attempt_count=record.attempt_count,
        completed_at=record.completed_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


async def _run_training(
    session: AsyncSession,
    record: WritingTrainingSession,
    submission: TopicTrainingSubmission,
) -> TopicTrainingSessionResponse:
    record.topic_prompt = submission.topic_prompt
    record.requirement_notes = submission.requirement_notes
    record.central_idea = submission.central_idea
    record.outline = submission.outline
    record.status = "running"
    record.feedback = None
    record.provider_key = None
    record.model_name = None
    record.completed_at = None
    await session.commit()

    try:
        generated = await generate_topic_training_feedback(submission)
    except TrainingGenerationError as exc:
        record.status = "failed"
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="这次训练反馈暂时没有完成，你填写的内容已经保留，可以直接重试。",
        ) from exc

    record.status = "completed"
    record.feedback = generated.output.model_dump(mode="json")
    record.provider_key = generated.provider_key
    record.model_name = generated.model_name
    record.completed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(record)
    return _response(record)


@router.get("/recommendations", response_model=TrainingRecommendationResponse)
async def get_training_recommendations(
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> TrainingRecommendationResponse:
    essays = list(
        (
            await session.scalars(
                select(Essay)
                .where(Essay.author_id == user.id, Essay.status == EssayStatus.EVALUATED)
                .order_by(Essay.created_at.asc(), Essay.version_no.asc())
                .options(selectinload(Essay.final_evaluations))
            )
        ).all()
    )
    records = [
        (essay, final)
        for essay in essays
        if (final := _latest_completed_final(essay)) is not None
    ]
    summary = build_growth_summary(records)
    recurring = summary.get("recurring_issues")
    if not isinstance(recurring, list) or not recurring:
        return TrainingRecommendationResponse(
            personalized=False,
            evaluated_work_count=int(summary.get("work_count") or 0),
            items=_general_recommendations(),
        )

    items: list[TrainingRecommendation] = []
    used_types: set[MicroExerciseType] = set()
    for issue in recurring:
        if not isinstance(issue, dict):
            continue
        exercise_type = _recommended_exercise(issue)
        if exercise_type in used_types:
            continue
        used_types.add(exercise_type)
        work_count = int(issue.get("work_count") or 0)
        label = str(issue.get("label") or "写作问题")
        items.append(
            TrainingRecommendation(
                exercise_type=exercise_type,
                title=MICRO_TRAINING_TITLES[exercise_type],
                reason=f"最近 {work_count} 篇不同作文都出现了“{label}”相关反馈。",
                personalized=True,
                evidence_work_count=work_count,
                source_label=label,
            )
        )
        if len(items) == 3:
            break
    return TrainingRecommendationResponse(
        personalized=bool(items),
        evaluated_work_count=int(summary.get("work_count") or 0),
        items=items or _general_recommendations(),
    )


@router.get("/micro-exercises/{exercise_type}", response_model=MicroTrainingTask)
async def get_micro_exercise(
    exercise_type: MicroExerciseType,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> MicroTrainingTask:
    completed_count = int(
        await session.scalar(
            select(func.count())
            .select_from(WritingTrainingSession)
            .where(
                WritingTrainingSession.author_id == user.id,
                WritingTrainingSession.training_type == f"micro:{exercise_type}",
                WritingTrainingSession.status == "completed",
            )
        )
        or 0
    )
    return get_micro_training_task(exercise_type, completed_count)


@router.post(
    "/micro-exercises",
    response_model=MicroTrainingResult,
    status_code=status.HTTP_201_CREATED,
)
async def submit_micro_exercise(
    payload: MicroTrainingSubmission,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> MicroTrainingResult:
    task = get_micro_training_task_by_id(payload.task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="这道训练题已经更新，请重新选择")
    if len(payload.response_text) < task.min_characters:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"再补充一些内容吧，建议至少写 {task.min_characters} 个字。",
        )
    if len(payload.response_text) > task.max_characters:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"这是一项短训练，请把内容控制在 {task.max_characters} 个字以内。",
        )

    record = WritingTrainingSession(
        author_id=user.id,
        training_type=f"micro:{task.exercise_type}",
        topic_prompt=task.prompt,
        requirement_notes=task.instruction,
        central_idea=payload.response_text,
        outline=task.context,
        status="running",
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    try:
        generated = await generate_micro_training_feedback(task, payload.response_text)
    except TrainingGenerationError as exc:
        record.status = "failed"
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="这次训练反馈暂时没有完成，你的作答仍在页面上，可以直接重试。",
        ) from exc

    record.status = "completed"
    record.feedback = generated.output.model_dump(mode="json")
    record.provider_key = generated.provider_key
    record.model_name = generated.model_name
    record.completed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(record)
    return MicroTrainingResult(
        id=record.id,
        task=task,
        response_text=record.central_idea,
        status="completed",
        feedback=MicroTrainingFeedback.model_validate(record.feedback),
        completed_at=record.completed_at,
        created_at=record.created_at,
    )


@router.get("/topic-analysis", response_model=TopicTrainingHistoryResponse)
async def list_topic_training_sessions(
    user: CurrentUser,
    limit: int = Query(default=12, ge=1, le=50),
    session: AsyncSession = Depends(get_db_session),
) -> TopicTrainingHistoryResponse:
    records = list(
        (
            await session.scalars(
                select(WritingTrainingSession)
                .where(
                    WritingTrainingSession.author_id == user.id,
                    WritingTrainingSession.training_type == "topic_and_idea",
                )
                .order_by(WritingTrainingSession.updated_at.desc())
                .limit(limit)
            )
        ).all()
    )
    return TopicTrainingHistoryResponse(items=[_response(record) for record in records])


@router.post(
    "/topic-analysis",
    response_model=TopicTrainingSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_topic_training_session(
    payload: TopicTrainingSubmission,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> TopicTrainingSessionResponse:
    record = WritingTrainingSession(
        author_id=user.id,
        topic_prompt=payload.topic_prompt,
        requirement_notes=payload.requirement_notes,
        central_idea=payload.central_idea,
        outline=payload.outline,
        status="running",
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return await _run_training(session, record, payload)


@router.put("/topic-analysis/{training_id}", response_model=TopicTrainingSessionResponse)
async def revise_topic_training_session(
    training_id: UUID,
    payload: TopicTrainingSubmission,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> TopicTrainingSessionResponse:
    record = await session.scalar(
        select(WritingTrainingSession).where(
            WritingTrainingSession.id == training_id,
            WritingTrainingSession.author_id == user.id,
        )
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="这次训练记录不存在")
    record.attempt_count += 1
    return await _run_training(session, record, payload)
