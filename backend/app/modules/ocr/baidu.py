from __future__ import annotations

import base64
import io
import time
from pathlib import Path
from threading import Lock
from typing import Any

import httpx
from PIL import Image

from app.core.config import settings
from app.modules.ocr.engine import RecognizedRegion


class BaiduOcrError(RuntimeError):
    pass


class BaiduOcrEngine:
    """Baidu handwriting OCR adapter with an in-memory access-token cache."""

    engine_name = "Baidu OCR handwriting"
    detection_model = "baidu-handwriting-detection"
    recognition_model = "baidu-handwriting"

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._token_expires_at = 0.0
        self._lock = Lock()

    def _get_access_token(self, client: httpx.Client) -> str:
        if self._access_token and time.monotonic() < self._token_expires_at:
            return self._access_token
        api_key = settings.baidu_ocr_api_key
        secret_key = settings.baidu_ocr_secret_key
        if api_key is None or secret_key is None:
            raise BaiduOcrError("Baidu OCR credentials are not configured")
        try:
            response = client.post(
                settings.baidu_ocr_token_url,
                params={
                    "grant_type": "client_credentials",
                    "client_id": api_key.get_secret_value(),
                    "client_secret": secret_key.get_secret_value(),
                },
            )
        except httpx.TimeoutException as exc:
            raise BaiduOcrError("Baidu OCR token request timed out") from exc
        except httpx.HTTPError as exc:
            raise BaiduOcrError("Baidu OCR token request could not be completed") from exc
        if response.is_error:
            raise BaiduOcrError(f"Baidu OCR token request failed with HTTP {response.status_code}")
        try:
            payload: dict[str, Any] = response.json()
            token = payload["access_token"]
            expires_in = int(payload.get("expires_in", 0))
        except (KeyError, TypeError, ValueError) as exc:
            raise BaiduOcrError("Baidu OCR token response was invalid") from exc
        if not isinstance(token, str) or not token:
            raise BaiduOcrError("Baidu OCR token response was invalid")
        self._access_token = token
        self._token_expires_at = time.monotonic() + max(expires_in - 300, 60)
        return token

    @staticmethod
    def _request_image(image_path: Path) -> tuple[bytes, float, float]:
        with Image.open(image_path) as opened:
            image = opened.convert("RGB")
            original_width, original_height = image.size
            longest_side = max(original_width, original_height)
            if longest_side > 4096:
                scale = 4096 / longest_side
                target_size = (
                    max(1, round(original_width * scale)),
                    max(1, round(original_height * scale)),
                )
                image = image.resize(target_size, Image.Resampling.LANCZOS)
            encoded = io.BytesIO()
            image.save(encoded, format="JPEG", quality=92, optimize=True)
            request_width, request_height = image.size
        return (
            encoded.getvalue(),
            original_width / request_width,
            original_height / request_height,
        )

    @staticmethod
    def _rectangle_polygon(location: dict[str, Any], scale_x: float, scale_y: float) -> list[list[float]] | None:
        try:
            left = float(location["left"]) * scale_x
            top = float(location["top"]) * scale_y
            width = float(location["width"]) * scale_x
            height = float(location["height"]) * scale_y
        except (KeyError, TypeError, ValueError):
            return None
        return [[left, top], [left + width, top], [left + width, top + height], [left, top + height]]

    @staticmethod
    def _vertex_polygon(vertices: Any, scale_x: float, scale_y: float) -> list[list[float]] | None:
        if not isinstance(vertices, list) or len(vertices) < 3:
            return None
        polygon: list[list[float]] = []
        try:
            for vertex in vertices:
                if not isinstance(vertex, dict):
                    return None
                polygon.append([float(vertex["x"]) * scale_x, float(vertex["y"]) * scale_y])
        except (KeyError, TypeError, ValueError):
            return None
        return polygon

    @staticmethod
    def _confidence(raw_probability: Any) -> float | None:
        if not isinstance(raw_probability, dict):
            return None
        value = raw_probability.get("average")
        if not isinstance(value, (int, float)):
            return None
        normalized = float(value)
        if normalized > 1:
            normalized /= 100
        return max(0.0, min(1.0, normalized))

    def recognize(self, image_path: Path) -> list[RecognizedRegion]:
        image_bytes, scale_x, scale_y = self._request_image(image_path)
        encoded_image = base64.b64encode(image_bytes)
        # The handwriting endpoint limits the Base64 image payload. Fail early with
        # an actionable message instead of sending a request the provider will reject.
        if len(encoded_image) > 8 * 1024 * 1024:
            raise BaiduOcrError("Baidu handwriting OCR input exceeds the provider size limit")
        timeout = httpx.Timeout(settings.baidu_ocr_timeout_seconds, connect=10.0)
        with self._lock, httpx.Client(timeout=timeout) as client:
            token = self._get_access_token(client)
            try:
                response = client.post(
                    settings.baidu_handwriting_url,
                    params={"access_token": token},
                    data={
                        "image": encoded_image.decode("ascii"),
                        "detect_direction": "true",
                        "vertexes_location": "true",
                        "probability": "true",
                    },
                )
            except httpx.TimeoutException as exc:
                raise BaiduOcrError("Baidu handwriting OCR request timed out") from exc
            except httpx.HTTPError as exc:
                raise BaiduOcrError("Baidu handwriting OCR request could not be completed") from exc
        if response.is_error:
            raise BaiduOcrError(f"Baidu handwriting OCR request failed with HTTP {response.status_code}")
        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            raise BaiduOcrError("Baidu handwriting OCR response was invalid") from exc
        if payload.get("error_code") is not None:
            raise BaiduOcrError(f"Baidu handwriting OCR returned error {payload['error_code']}")
        records = payload.get("words_result")
        if not isinstance(records, list):
            raise BaiduOcrError("Baidu handwriting OCR response was invalid")

        regions: list[RecognizedRegion] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            text = str(record.get("words", "")).strip()
            polygon = self._vertex_polygon(record.get("vertexes_location"), scale_x, scale_y)
            polygon = polygon or self._rectangle_polygon(record.get("location", {}), scale_x, scale_y)
            if not text or polygon is None:
                continue
            regions.append(
                RecognizedRegion(
                    text=text,
                    polygon=[[round(x, 2), round(y, 2)] for x, y in polygon],
                    confidence=self._confidence(record.get("probability")),
                )
            )
        return regions
