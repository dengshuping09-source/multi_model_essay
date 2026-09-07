from __future__ import annotations

from importlib.util import find_spec

from app.core.config import settings
from app.modules.reviews.service import provider_statuses


def get_service_statuses() -> list[dict[str, object]]:
    """Return non-invasive readiness information without spending API quota."""
    model_services = [
        {
            "key": item.key,
            "kind": "model",
            "display_name": item.display_name,
            "model_name": item.model_name,
            "configured": item.configured,
            "available": item.configured,
            "detail": (
                "API credentials are configured. Availability is confirmed when a review is requested."
                if item.configured
                else "API credentials are not configured."
            ),
        }
        for item in provider_statuses()
    ]
    paddle_available = find_spec("paddleocr") is not None
    baidu_configured = (
        settings.baidu_ocr_api_key is not None and settings.baidu_ocr_secret_key is not None
    )
    return [
        *model_services,
        {
            "key": "paddle",
            "kind": "ocr",
            "display_name": "PaddleOCR",
            "model_name": settings.ocr_recognition_model,
            "configured": paddle_available,
            "available": paddle_available,
            "detail": (
                "Local OCR package is ready; models load on the first recognition request."
                if paddle_available
                else "The PaddleOCR package is not installed in the backend environment."
            ),
        },
        {
            "key": "baidu",
            "kind": "ocr",
            "display_name": "Baidu OCR",
            "model_name": "handwriting",
            "configured": baidu_configured,
            "available": baidu_configured,
            "detail": (
                "Credentials are configured. A token is requested only when OCR starts."
                if baidu_configured
                else "Baidu OCR credentials are not configured."
            ),
        },
    ]
