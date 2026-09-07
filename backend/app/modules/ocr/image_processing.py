from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:
    pass

from app.db.models import ImageQualityStatus

PROCESSOR_VERSION = "opencv-v1"
ANALYSIS_MAX_DIMENSION = 1600


@dataclass(frozen=True)
class ImageProcessingResult:
    status: ImageQualityStatus
    quality_score: int
    blur_score: float
    brightness: float
    contrast: float
    shadow_score: float
    skew_angle: float
    rotation_degrees: int
    page_detected: bool
    page_polygon: list[list[float]] | None
    warnings: list[str]
    applied_operations: list[str]
    detail: str
    processed_path: Path | None
    processed_width: int | None
    processed_height: int | None
    original_to_processed_matrix: list[list[float]]
    processed_to_original_matrix: list[list[float]]


def _read_image(path: Path) -> np.ndarray:
    encoded = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    if image is not None:
        return image

    # OpenCV does not reliably decode HEIC/HEIF, AVIF, multi-page TIFF, or
    # animated images on every platform. Pillow (with pillow-heif registered
    # by the upload module) decodes the first still frame and gives OpenCV a
    # consistent BGR array without changing the preserved original upload.
    try:
        with Image.open(path) as opened:
            opened.seek(0)
            rgb = ImageOps.exif_transpose(opened).convert("RGB")
            return cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR)
    except (OSError, ValueError) as exc:
        raise ValueError("无法读取上传图片") from exc


def _write_png(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    if not success:
        raise OSError("处理后图片编码失败")
    encoded.tofile(path)


def _exif_rotation(path: Path) -> int:
    try:
        with Image.open(path) as image:
            orientation = image.getexif().get(274)
    except (OSError, ValueError):
        return 0
    return {3: 180, 6: 90, 8: 270}.get(orientation, 0)


def _matrix_list(matrix: np.ndarray) -> list[list[float]]:
    return [[round(float(value), 8) for value in row] for row in matrix]


def _rotate_quarter_turn(
    image: np.ndarray, degrees: int
) -> tuple[np.ndarray, np.ndarray]:
    height, width = image.shape[:2]
    if degrees == 90:
        matrix = np.array([[0, -1, height - 1], [1, 0, 0], [0, 0, 1]], dtype=np.float64)
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE), matrix
    if degrees == 180:
        matrix = np.array(
            [[-1, 0, width - 1], [0, -1, height - 1], [0, 0, 1]],
            dtype=np.float64,
        )
        return cv2.rotate(image, cv2.ROTATE_180), matrix
    if degrees == 270:
        matrix = np.array([[0, 1, 0], [-1, 0, width - 1], [0, 0, 1]], dtype=np.float64)
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE), matrix
    return image, np.eye(3, dtype=np.float64)


def _analysis_gray(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    scale = min(1.0, ANALYSIS_MAX_DIMENSION / max(height, width))
    if scale < 1.0:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _content_quarter_turn(gray: np.ndarray) -> int:
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        15,
    )
    horizontal_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (max(20, gray.shape[1] // 25), 1)
    )
    vertical_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (1, max(20, gray.shape[0] // 25))
    )
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
    horizontal_ratio = float(np.count_nonzero(horizontal)) / horizontal.size
    vertical_ratio = float(np.count_nonzero(vertical)) / vertical.size

    if vertical_ratio > 0.006 and vertical_ratio > horizontal_ratio * 1.8:
        return 90
    return 0


def _order_points(points: np.ndarray) -> np.ndarray:
    ordered = np.zeros((4, 2), dtype=np.float32)
    point_sum = points.sum(axis=1)
    point_difference = np.diff(points, axis=1).reshape(-1)
    ordered[0] = points[np.argmin(point_sum)]
    ordered[2] = points[np.argmax(point_sum)]
    ordered[1] = points[np.argmin(point_difference)]
    ordered[3] = points[np.argmax(point_difference)]
    return ordered


def _detect_page(image: np.ndarray) -> tuple[np.ndarray | None, float]:
    height, width = image.shape[:2]
    scale = min(1.0, 1400 / max(height, width))
    resized = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.morphologyEx(
        edges, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    )
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = resized.shape[0] * resized.shape[1]

    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:12]:
        area_ratio = cv2.contourArea(contour) / image_area
        if area_ratio < 0.25:
            break
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(polygon) == 4 and cv2.isContourConvex(polygon):
            points = _order_points(polygon.reshape(4, 2).astype(np.float32) / scale)
            return points, float(area_ratio)
    return None, 0.0


def _needs_perspective_transform(
    polygon: np.ndarray, area_ratio: float, image_shape: tuple[int, ...]
) -> bool:
    height, width = image_shape[:2]
    image_corners = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    corner_distance = np.linalg.norm(polygon - image_corners, axis=1).mean()
    diagonal = np.hypot(width, height)
    return area_ratio < 0.92 or corner_distance / diagonal > 0.035


def _perspective_transform(
    image: np.ndarray, polygon: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    top_left, top_right, bottom_right, bottom_left = polygon
    width = int(
        max(
            np.linalg.norm(bottom_right - bottom_left),
            np.linalg.norm(top_right - top_left),
        )
    )
    height = int(
        max(
            np.linalg.norm(top_right - bottom_right),
            np.linalg.norm(top_left - bottom_left),
        )
    )
    if width < 100 or height < 100:
        return image, np.eye(3, dtype=np.float64)

    destination = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(polygon, destination)
    return (
        cv2.warpPerspective(
            image,
            transform,
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255),
        ),
        transform.astype(np.float64),
    )


def _estimate_skew(gray: np.ndarray) -> float:
    inverted = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        15,
    )
    lines = cv2.HoughLinesP(
        inverted,
        1,
        np.pi / 180,
        threshold=60,
        minLineLength=max(40, gray.shape[1] // 6),
        maxLineGap=20,
    )
    if lines is None:
        return 0.0

    angles: list[float] = []
    for x1, y1, x2, y2 in lines[:, 0]:
        angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        if -20 <= angle <= 20:
            angles.append(angle)
    return float(np.median(angles)) if angles else 0.0


def _rotate_bound(image: np.ndarray, angle: float) -> tuple[np.ndarray, np.ndarray]:
    height, width = image.shape[:2]
    center = (width / 2, height / 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    cosine = abs(matrix[0, 0])
    sine = abs(matrix[0, 1])
    output_width = int(height * sine + width * cosine)
    output_height = int(height * cosine + width * sine)
    matrix[0, 2] += output_width / 2 - center[0]
    matrix[1, 2] += output_height / 2 - center[1]
    transformed = cv2.warpAffine(
        image,
        matrix,
        (output_width, output_height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )
    homogeneous = np.vstack((matrix, np.array([0, 0, 1], dtype=np.float64)))
    return transformed, homogeneous


def _shadow_score(gray: np.ndarray) -> float:
    scale = min(1.0, 320 / max(gray.shape))
    sample = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    background = cv2.GaussianBlur(sample, (0, 0), sigmaX=20, sigmaY=20)
    mean = max(float(background.mean()), 1.0)
    return float(background.std() / mean)


def _edge_density(gray: np.ndarray) -> float:
    edges = cv2.Canny(gray, 50, 150)
    return float(np.count_nonzero(edges) / edges.size)


def _improve_illumination(image: np.ndarray, strong_shadow: bool) -> np.ndarray:
    if strong_shadow:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        background = cv2.GaussianBlur(gray, (0, 0), sigmaX=25, sigmaY=25)
        normalized = cv2.divide(gray, np.maximum(background, 1), scale=235)
        normalized = cv2.createCLAHE(clipLimit=1.8, tileGridSize=(8, 8)).apply(normalized)
        return cv2.cvtColor(normalized, cv2.COLOR_GRAY2BGR)

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lightness, channel_a, channel_b = cv2.split(lab)
    lightness = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8)).apply(lightness)
    return cv2.cvtColor(cv2.merge((lightness, channel_a, channel_b)), cv2.COLOR_LAB2BGR)


def analyze_and_preprocess_image(
    original_path: Path,
    processed_path: Path,
    max_image_pixels: int,
    force_ocr_input_normalization: bool = False,
) -> ImageProcessingResult:
    image = _read_image(original_path)
    if image.shape[0] * image.shape[1] > max_image_pixels:
        raise ValueError("图片像素尺寸过大")

    operations: list[str] = []
    warnings: list[str] = []
    rotation = _exif_rotation(original_path)
    if not rotation:
        rotation = _content_quarter_turn(_analysis_gray(image))
    working, original_to_working = _rotate_quarter_turn(image, rotation)
    if rotation:
        operations.append("方向纠正")
        warnings.append("检测到图片方向需要纠正")

    page_polygon_array, page_area_ratio = _detect_page(working)
    page_detected = page_polygon_array is not None
    page_polygon = (
        [[round(float(x), 2), round(float(y), 2)] for x, y in page_polygon_array]
        if page_polygon_array is not None
        else None
    )
    quality_image = working
    if page_polygon_array is not None:
        quality_image, _ = _perspective_transform(working, page_polygon_array)
    gray = _analysis_gray(quality_image)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    contrast = float(gray.std())
    shadow_score = _shadow_score(gray)
    edge_density = _edge_density(gray)
    skew_angle = _estimate_skew(gray)

    severe: list[str] = []
    score = 100
    if blur_score < 30:
        severe.append("图片严重模糊，请保持镜头稳定并重新拍摄")
        score -= 55
    elif blur_score < 90:
        warnings.append("图片清晰度偏低，文字边缘可能影响识别")
        score -= 22

    if brightness < 35:
        severe.append("图片严重欠曝，请在光线充足处重新拍摄")
        score -= 45
    elif brightness < 75:
        warnings.append("图片偏暗，建议增加环境光线")
        score -= 16
    elif brightness > 247 or (brightness > 238 and contrast < 12):
        severe.append("图片过曝且文字对比不足，请避免强光直射")
        score -= 45
    elif brightness > 228 and contrast < 28:
        warnings.append("图片偏亮，部分浅色笔迹可能不清晰")
        score -= 12

    if contrast < 9:
        severe.append("图片几乎没有可辨识内容，请重新拍摄完整作文页面")
        score -= 45
    elif contrast < 25:
        warnings.append("文字与纸张对比度偏低")
        score -= 14

    if shadow_score > 0.16:
        warnings.append("页面存在明显阴影或光照不均")
        score -= 12

    if abs(skew_angle) > 1.2:
        warnings.append("页面存在明显倾斜")
        score -= min(18, int(abs(skew_angle) * 1.5))

    if not page_detected:
        if edge_density < 0.003:
            severe.append("无法判断有效作文页面，请确保纸张完整出现在画面中")
            score -= 35
        elif not (120 <= brightness <= 245 and contrast >= 25 and edge_density >= 0.01):
            warnings.append("未检测到完整纸张边界，将保留原始画面")
            score -= 8

    needs_perspective = bool(
        page_polygon_array is not None
        and _needs_perspective_transform(page_polygon_array, page_area_ratio, working.shape)
    )
    if needs_perspective:
        warnings.append("页面边缘存在透视变形")
        score -= 10

    score = max(0, min(100, score))
    if severe:
        return ImageProcessingResult(
            status=ImageQualityStatus.UNUSABLE,
            quality_score=score,
            blur_score=blur_score,
            brightness=brightness,
            contrast=contrast,
            shadow_score=shadow_score,
            skew_angle=skew_angle,
            rotation_degrees=rotation,
            page_detected=page_detected,
            page_polygon=page_polygon,
            warnings=severe + warnings,
            applied_operations=[],
            detail="当前图片不适合 OCR，请根据提示重新拍摄后提交。",
            processed_path=None,
            processed_width=None,
            processed_height=None,
            original_to_processed_matrix=_matrix_list(np.eye(3)),
            processed_to_original_matrix=_matrix_list(np.eye(3)),
        )

    if needs_perspective and page_polygon_array is not None:
        working, perspective_matrix = _perspective_transform(working, page_polygon_array)
        original_to_working = perspective_matrix @ original_to_working
        operations.append("页面检测与透视矫正")

    corrected_skew_angle = _estimate_skew(_analysis_gray(working))
    if abs(corrected_skew_angle) > 1.2:
        working, deskew_matrix = _rotate_bound(working, corrected_skew_angle)
        original_to_working = deskew_matrix @ original_to_working
        operations.append("倾斜校正")

    processed_gray = _analysis_gray(working)
    processed_shadow_score = _shadow_score(processed_gray)
    needs_illumination = (
        processed_shadow_score > 0.12
        or float(processed_gray.mean()) < 90
        or float(processed_gray.std()) < 25
    )
    if needs_illumination:
        working = _improve_illumination(
            working, strong_shadow=processed_shadow_score > 0.16
        )
        operations.append("亮度与阴影改善")

    processed_output: Path | None = None
    processed_width: int | None = None
    processed_height: int | None = None
    if force_ocr_input_normalization:
        operations.append("OCR 输入标准化")
    if operations:
        _write_png(processed_path, working)
        processed_output = processed_path
        processed_height, processed_width = working.shape[:2]

    if processed_output:
        original_to_processed = original_to_working
        processed_to_original = np.linalg.inv(original_to_processed)
    else:
        original_to_processed = np.eye(3, dtype=np.float64)
        processed_to_original = np.eye(3, dtype=np.float64)

    status = ImageQualityStatus.GOOD if not warnings else ImageQualityStatus.IMPROVABLE
    if status is ImageQualityStatus.GOOD:
        detail = "图片质量良好，无需额外处理，可直接用于后续 OCR。"
    elif operations:
        detail = "图片可用于 OCR，已按需完成必要的图像优化。"
    else:
        detail = "图片可以保留，但建议按提示重新拍摄以获得更稳定的 OCR 效果。"

    return ImageProcessingResult(
        status=status,
        quality_score=score,
        blur_score=blur_score,
        brightness=brightness,
        contrast=contrast,
        shadow_score=shadow_score,
        skew_angle=skew_angle,
        rotation_degrees=rotation,
        page_detected=page_detected,
        page_polygon=page_polygon,
        warnings=warnings,
        applied_operations=operations,
        detail=detail,
        processed_path=processed_output,
        processed_width=processed_width,
        processed_height=processed_height,
        original_to_processed_matrix=_matrix_list(original_to_processed),
        processed_to_original_matrix=_matrix_list(processed_to_original),
    )
