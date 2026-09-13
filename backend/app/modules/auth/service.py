from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import hash_password, new_session_token, token_digest, verify_password
from app.db.models import User, UserSession


class AuthenticationError(RuntimeError):
    pass


class RegistrationError(RuntimeError):
    pass


async def register_user(session: AsyncSession, email: str, display_name: str, password: str) -> User:
    user = User(
        email=email.strip().lower(),
        display_name=display_name.strip(),
        password_hash=hash_password(password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise RegistrationError("这个邮箱已经注册，请直接登录") from exc
    return user


async def create_session(session: AsyncSession, email: str, password: str) -> tuple[User, str, datetime]:
    user = await session.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise AuthenticationError("邮箱或密码不正确")
    token = new_session_token()
    expires_at = datetime.now(timezone.utc) + settings.session_ttl
    session.add(UserSession(user_id=user.id, token_hash=token_digest(token), expires_at=expires_at))
    await session.commit()
    return user, token, expires_at


async def get_user_for_token(session: AsyncSession, token: str) -> User:
    now = datetime.now(timezone.utc)
    user_session = await session.scalar(
        select(UserSession)
        .where(
            UserSession.token_hash == token_digest(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
        .options(selectinload(UserSession.user))
    )
    if user_session is None or not user_session.user.is_active:
        raise AuthenticationError("请先登录后再继续")
    return user_session.user


async def revoke_session(session: AsyncSession, token: str) -> None:
    current = await session.scalar(
        select(UserSession).where(
            UserSession.token_hash == token_digest(token), UserSession.revoked_at.is_(None)
        )
    )
    if current is not None:
        current.revoked_at = datetime.now(timezone.utc)
        await session.commit()


async def update_user_profile(
    session: AsyncSession,
    user: User,
    display_name: str,
    grade_level: str | None,
    default_genre: str | None,
) -> User:
    user.display_name = display_name.strip()
    user.grade_level = (grade_level or "").strip() or None
    user.default_genre = (default_genre or "").strip() or None
    await session.commit()
    return user


async def change_user_password(
    session: AsyncSession,
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    if not verify_password(current_password, user.password_hash):
        raise AuthenticationError("当前密码不正确")
    user.password_hash = hash_password(new_password)
    await session.commit()
