from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import logging
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any, Literal, Protocol

from app.core.config import settings


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecognizedRegion:
    text: str
    polygon: list[list[float]]
    confidence: float | None


class OcrEngine(Protocol):
    engine_name: str
    detection_model: str
    recognition_model: str

    def recognize(self, image_path: Path) -> list[RecognizedRegion]: ...


class PaddleOcrEngine:
    engine_name = "PaddleOCR 3.x"

    def __init__(self) -> None:
        self.detection_model = settings.ocr_detection_model
        self.recognition_model = settings.ocr_recognition_model
        self._pipeline: Any | None = None
        self._lock = Lock()

    def _get_pipeline(self) -> Any:
        if self._pipeline is None:
            from paddleocr import PaddleOCR

            started_at = perf_counter()
            self._pipeline = PaddleOCR(
                text_detection_model_name=self.detection_model,
                text_recognition_model_name=self.recognition_model,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                device=settings.ocr_device,
                enable_mkldnn=settings.ocr_enable_mkldnn,
                cpu_threads=settings.ocr_cpu_threads,
            )
            logger.info(
                "ocr_engine_initialized engine=paddle detection_model=%s recognition_model=%s elapsed_ms=%d",
                self.detection_model,
                self.recognition_model,
                round((perf_counter() - started_at) * 1000),
            )
        return self._pipeline

    def recognize(self, image_path: Path) -> list[RecognizedRegion]:
        with self._lock:
            predictions = self._get_pipeline().predict(
                str(image_path),
                text_rec_score_thresh=0.0,
            )
            regions: list[RecognizedRegion] = []
            for prediction in predictions:
                payload = prediction.json
                result = payload.get("res", payload)
                texts = result.get("rec_texts", [])
                scores = result.get("rec_scores", [])
                polygons = result.get("rec_polys", [])
                for text, score, polygon in zip(texts, scores, polygons, strict=False):
                    normalized_text = str(text).strip()
                    if not normalized_text:
                        continue
                    regions.append(
                        RecognizedRegion(
                            text=normalized_text,
                            polygon=[
                                [round(float(point[0]), 2), round(float(point[1]), 2)]
                                for point in polygon
                            ],
                            confidence=max(0.0, min(1.0, float(score))),
                        )
                    )
            return regions


OcrEngineKey = Literal["paddle", "baidu"]


@lru_cache
def get_paddle_ocr_engine() -> PaddleOcrEngine:
    return PaddleOcrEngine()


@lru_cache
def get_baidu_ocr_engine() -> OcrEngine:
    from app.modules.ocr.baidu import BaiduOcrEngine

    return BaiduOcrEngine()


def get_default_ocr_engine_key() -> OcrEngineKey:
    """Return the configured provider without importing either OCR runtime."""
    return settings.ocr_default_engine


def get_ocr_engine(engine_key: OcrEngineKey | None = None) -> OcrEngine:
    engine_key = engine_key or get_default_ocr_engine_key()
    if engine_key == "paddle":
        return get_paddle_ocr_engine()
    return get_baidu_ocr_engine()
