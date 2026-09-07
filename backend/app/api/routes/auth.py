from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Annotated

from anyio import to_thread
from fastapi import APIRouter, Depends, File, Header, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.config import settings
from app.db.session import get_db_session
from app.modules.auth.service import AuthenticationError, RegistrationError, change_user_password, create_session, register_user, revoke_session, update_user_profile
from app.modules.essays.service import cleanup_user_session_essays
from app.schemas.auth import LoginRequest, PasswordChangeRequest, RegisterRequest, SessionResponse, UserProfileUpdateRequest, UserResponse

router = APIRouter(tags=["auth"])


def _user_response(user: CurrentUser) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        grade_level=user.grade_level,
        default_genre=user.default_genre,
        avatar_available=_avatar_path(user.id).is_file(),
        created_at=user.created_at,
    )


def _avatar_path(user_id) -> Path:
    return (settings.upload_dir.resolve().parent / "avatars" / f"{user_id}.png").resolve()


def _save_avatar(content: bytes, destination: Path) -> None:
    try:
        with Image.open(BytesIO(content)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP", "HEIF", "AVIF"}:
                raise ValueError("unsupported avatar format")
            image = ImageOps.exif_transpose(source).convert("RGBA")
            image.thumbnail((512, 512), Image.Resampling.LANCZOS)
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(".tmp.png")
            image.save(temporary, format="PNG", optimize=True)
            temporary.replace(destination)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("请选择有效的 JPG、PNG、WebP、HEIC 或 AVIF 图片") from exc


@router.post("/register", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_db_session)) -> SessionResponse:
    try:
        user = await register_user(session, payload.email, payload.display_name, payload.password)
        user, token, expires_at = await create_session(session, user.email, payload.password)
    except RegistrationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return SessionResponse(access_token=token, expires_at=expires_at, user=_user_response(user))


@router.post("/login", response_model=SessionResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db_session)) -> SessionResponse:
    try:
        user, token, expires_at = await create_session(session, payload.email, payload.password)
        await cleanup_user_session_essays(session, user.id)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return SessionResponse(access_token=token, expires_at=expires_at, user=_user_response(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def logout(
    user: CurrentUser,
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await cleanup_user_session_essays(session, user.id)
    if authorization is not None:
        await revoke_session(session, authorization.removeprefix("Bearer ").strip())
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser, session: AsyncSession = Depends(get_db_session)) -> UserResponse:
    await cleanup_user_session_essays(session, user.id)
    return _user_response(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UserProfileUpdateRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    updated = await update_user_profile(
        session,
        user,
        payload.display_name,
        payload.grade_level,
        payload.default_genre,
    )
    return _user_response(updated)


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def update_password(
    payload: PasswordChangeRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    try:
        await change_user_password(
            session, user, payload.current_password, payload.new_password
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/avatar", response_model=UserResponse)
async def update_avatar(
    user: CurrentUser,
    avatar: Annotated[UploadFile, File()],
) -> UserResponse:
    content = await avatar.read(2 * 1024 * 1024 + 1)
    await avatar.close()
    if not content or len(content) > 2 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="头像图片需小于 2 MB",
        )
    try:
        await to_thread.run_sync(_save_avatar, content, _avatar_path(user.id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _user_response(user)


@router.get("/me/avatar", response_class=FileResponse)
async def get_avatar(user: CurrentUser) -> FileResponse:
    path = _avatar_path(user.id)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="尚未设置头像")
    return FileResponse(path, media_type="image/png", filename="avatar.png")
