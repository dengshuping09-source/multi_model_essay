from __future__ import annotations

import os
import shutil
import warnings
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4

import aiofiles
from anyio import to_thread
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # The pinned runtime dependency registers HEIF support in production.
    pass

CHUNK_SIZE = 1024 * 1024
IMAGE_FORMATS = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
    "AVIF": (".avif", "image/avif"),
    "HEIF": (".heif", "image/heif"),
    "HEIC": (".heic", "image/heic"),
    "BMP": (".bmp", "image/bmp"),
    "TIFF": (".tiff", "image/tiff"),
    # Animated originals are retained, while the first frame is normalised to
    # a PNG OCR input later in the upload flow.
    "GIF": (".gif", "image/gif"),
}


class UploadValidationError(ValueError):
    pass


@dataclass(frozen=True)
class StoredImage:
    original_name: str
    storage_key: str
    mime_type: str
    size_bytes: int
    width: int
    height: int
    image_format: str
    is_animated: bool
    absolute_path: Path


def _safe_original_name(filename: str | None) -> str:
    if not filename:
        raise UploadValidationError("图片文件名不能为空")

    name = PurePosixPath(filename.replace("\\", "/")).name
    if not name or "\x00" in name or len(name) > 255:
        raise UploadValidationError("图片文件名无效或过长")
    return name


def _looks_like_html(path: Path) -> bool:
    try:
        prefix = path.read_bytes()[:512].lstrip().lower()
    except OSError:
        return False
    return prefix.startswith((b"<!doctype html", b"<html", b"<head", b"<body"))


def _inspect_image(path: Path, max_image_pixels: int) -> tuple[str, int, int, bool]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                image_format = (image.format or "").upper()
                width, height = image.size
                is_animated = bool(getattr(image, "is_animated", False))
                image.verify()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise UploadValidationError("图片像素尺寸过大") from None
    except (UnidentifiedImageError, OSError, SyntaxError):
        if _looks_like_html(path):
            raise UploadValidationError("这个文件不是有效图片，请重新选择作文照片") from None
        raise UploadValidationError("这个文件不是有效图片，请重新选择作文照片") from None

    if image_format not in IMAGE_FORMATS:
        raise UploadValidationError("暂不支持这种图片格式，请重新选择作文照片")
    if width <= 0 or height <= 0 or width * height > max_image_pixels:
        raise UploadValidationError("图片像素尺寸无效或过大")

    return image_format, width, height, is_animated


async def save_uploaded_image(
    upload: UploadFile,
    essay_id: UUID,
    upload_root: Path,
    max_size_bytes: int,
    max_image_pixels: int,
) -> StoredImage:
    original_name = _safe_original_name(upload.filename)

    essay_directory = upload_root / str(essay_id)
    essay_directory.mkdir(parents=True, exist_ok=True)
    temporary_path = essay_directory / f".{uuid4().hex}.upload"
    size_bytes = 0

    try:
        async with aiofiles.open(temporary_path, "wb") as destination:
            while chunk := await upload.read(CHUNK_SIZE):
                size_bytes += len(chunk)
                if size_bytes > max_size_bytes:
                    raise UploadValidationError(
                        f"单张图片不能超过 {max_size_bytes // (1024 * 1024)} MB"
                    )
                await destination.write(chunk)

        if size_bytes == 0:
            raise UploadValidationError("不能上传空图片文件")

        image_format, width, height, is_animated = await to_thread.run_sync(
            _inspect_image, temporary_path, max_image_pixels
        )
        extension, actual_mime_type = IMAGE_FORMATS[image_format]
        stored_name = f"{uuid4().hex}{extension}"
        final_path = essay_directory / stored_name
        await to_thread.run_sync(os.replace, temporary_path, final_path)

        return StoredImage(
            original_name=original_name,
            storage_key=f"{essay_id}/{stored_name}",
            mime_type=actual_mime_type,
            size_bytes=size_bytes,
            width=width,
            height=height,
            image_format=image_format,
            is_animated=is_animated,
            absolute_path=final_path,
        )
    finally:
        await upload.close()
        if temporary_path.exists():
            temporary_path.unlink()
        try:
            essay_directory.rmdir()
        except OSError:
            pass


def remove_stored_images(images: list[StoredImage]) -> None:
    remove_artifact_paths([image.absolute_path for image in images])


def remove_artifact_paths(paths: list[Path]) -> None:
    directories = {path.parent for path in paths}
    for path in paths:
        path.unlink(missing_ok=True)

    for directory in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass
        try:
            directory.parent.rmdir()
        except OSError:
            pass


def remove_essay_upload_directory(upload_root: Path, essay_id: UUID) -> None:
    root = upload_root.resolve()
    target = (root / str(essay_id)).resolve()
    if target == root or root not in target.parents:
        raise ValueError("Refusing to remove an upload path outside the configured root")
    if target.is_dir():
        shutil.rmtree(target)
