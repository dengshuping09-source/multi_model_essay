from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from app.db.models import ImageQualityStatus
from app.modules.ocr.image_processing import analyze_and_preprocess_image


def document_image() -> np.ndarray:
    image = np.full((900, 700, 3), 245, dtype=np.uint8)
    cv2.rectangle(image, (35, 25), (665, 875), (215, 215, 215), 3)
    for y in range(90, 830, 42):
        cv2.line(image, (90, y), (610, y), (55, 55, 55), 3)
    return image


def write_image(path: Path, image: np.ndarray) -> None:
    success, encoded = cv2.imencode(path.suffix, image)
    assert success
    encoded.tofile(path)


def perspective_document() -> np.ndarray:
    document = document_image()
    canvas = np.full((1050, 900, 3), 55, dtype=np.uint8)
    source = np.float32([[0, 0], [699, 0], [699, 899], [0, 899]])
    destination = np.float32([[150, 80], [785, 130], [720, 970], [90, 900]])
    transform = cv2.getPerspectiveTransform(source, destination)
    warped = cv2.warpPerspective(document, transform, (900, 1050))
    mask = cv2.warpPerspective(
        np.full(document.shape[:2], 255, dtype=np.uint8), transform, (900, 1050)
    )
    canvas[mask > 0] = warped[mask > 0]
    return canvas


def test_clear_document_keeps_original_unchanged(tmp_path: Path) -> None:
    original = tmp_path / "clear.png"
    processed = tmp_path / "clear-processed.png"
    write_image(original, document_image())
    original_bytes = original.read_bytes()

    result = analyze_and_preprocess_image(original, processed, 40_000_000)

    assert result.status is ImageQualityStatus.GOOD
    assert result.quality_score == 100
    assert not result.applied_operations
    assert result.processed_path is None
    assert not processed.exists()
    assert original.read_bytes() == original_bytes
    assert np.allclose(result.original_to_processed_matrix, np.eye(3))
    assert np.allclose(result.processed_to_original_matrix, np.eye(3))


def test_perspective_document_is_rectified_without_touching_original(tmp_path: Path) -> None:
    original = tmp_path / "perspective.png"
    processed = tmp_path / "perspective-processed.png"
    write_image(original, perspective_document())
    original_bytes = original.read_bytes()

    result = analyze_and_preprocess_image(original, processed, 40_000_000)

    assert result.status is ImageQualityStatus.IMPROVABLE
    assert result.page_detected
    assert "页面检测与透视矫正" in result.applied_operations
    assert processed.is_file()
    assert original.read_bytes() == original_bytes
    forward = np.asarray(result.original_to_processed_matrix)
    inverse = np.asarray(result.processed_to_original_matrix)
    assert not np.allclose(forward, np.eye(3))
    assert np.allclose(inverse @ forward, np.eye(3), atol=1e-5)


def test_exif_orientation_is_applied_to_processed_copy(tmp_path: Path) -> None:
    raw_image = cv2.rotate(document_image(), cv2.ROTATE_90_COUNTERCLOCKWISE)
    original = tmp_path / "camera-orientation.jpg"
    exif = Image.Exif()
    exif[274] = 6
    Image.fromarray(cv2.cvtColor(raw_image, cv2.COLOR_BGR2RGB)).save(
        original, format="JPEG", quality=95, exif=exif
    )
    processed = tmp_path / "camera-orientation-processed.png"

    result = analyze_and_preprocess_image(original, processed, 40_000_000)

    assert result.rotation_degrees == 90
    assert "方向纠正" in result.applied_operations
    assert processed.is_file()
    assert result.processed_height and result.processed_width
    assert result.processed_height > result.processed_width


@pytest.mark.parametrize("problem", ["blur", "dark"])
def test_unusable_images_return_retake_guidance(tmp_path: Path, problem: str) -> None:
    image = document_image()
    if problem == "blur":
        image = cv2.GaussianBlur(image, (51, 51), 0)
    else:
        image = (image.astype(np.float32) * 0.12).astype(np.uint8)
    original = tmp_path / f"{problem}.png"
    processed = tmp_path / f"{problem}-processed.png"
    write_image(original, image)

    result = analyze_and_preprocess_image(original, processed, 40_000_000)

    assert result.status is ImageQualityStatus.UNUSABLE
    assert "重新" in result.detail
    assert result.processed_path is None
    assert not processed.exists()


def test_shadow_and_skew_trigger_only_needed_adjustments(tmp_path: Path) -> None:
    shadow = document_image()
    gradient = np.linspace(0.35, 1.0, shadow.shape[1], dtype=np.float32)[None, :, None]
    shadow = (shadow.astype(np.float32) * gradient).clip(0, 255).astype(np.uint8)
    shadow_path = tmp_path / "shadow.png"
    write_image(shadow_path, shadow)

    shadow_result = analyze_and_preprocess_image(
        shadow_path, tmp_path / "shadow-processed.png", 40_000_000
    )

    assert shadow_result.status is ImageQualityStatus.IMPROVABLE
    assert shadow_result.applied_operations == ["亮度与阴影改善"]

    skewed = document_image()
    height, width = skewed.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), -6, 1.0)
    skewed = cv2.warpAffine(
        skewed,
        matrix,
        (width, height),
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )
    skew_path = tmp_path / "skew.png"
    write_image(skew_path, skewed)

    skew_result = analyze_and_preprocess_image(
        skew_path, tmp_path / "skew-processed.png", 40_000_000
    )

    assert skew_result.status is ImageQualityStatus.IMPROVABLE
    assert abs(skew_result.skew_angle) >= 4
    assert "倾斜校正" in skew_result.applied_operations
