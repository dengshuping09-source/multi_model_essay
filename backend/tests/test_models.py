from uuid import uuid4

from sqlalchemy.orm import configure_mappers

from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.models import Essay


def test_core_database_tables_are_registered() -> None:
    configure_mappers()

    assert set(Base.metadata.tables) == {
        "ai_annotations",
        "essay_sentences",
        "essay_sources",
        "essays",
        "final_evaluation_reviews",
        "final_evaluations",
        "image_quality_analyses",
        "model_reviews",
        "material_favorites",
        "ocr_block_corrections",
        "ocr_blocks",
        "ocr_corrections",
        "ocr_page_results",
        "ocr_runs",
        "score_evidence",
        "sentence_ocr_mappings",
        "reference_assessments",
        "review_batches",
        "review_rechecks",
        "user_sessions",
        "users",
        "writing_training_sessions",
    }


def test_new_essay_defaults_to_its_own_first_version() -> None:
    essay = Essay(author_id=uuid4())

    assert essay.root_essay_id == essay.id
    assert essay.parent_essay_id is None
    assert essay.version_no == 1
