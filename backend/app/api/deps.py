from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.db.models import User
from app.db.session import get_session_factory
from app.modules.auth.service import AuthenticationError, get_user_for_token


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录后再继续")
    try:
        async with get_session_factory()() as session:
            return await get_user_for_token(session, authorization.removeprefix("Bearer ").strip())
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效，请重新登录") from exc


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    """Allow public reading endpoints to enrich responses for signed-in students."""

    if authorization is None or not authorization.startswith("Bearer "):
        return None
    try:
        async with get_session_factory()() as session:
            return await get_user_for_token(session, authorization.removeprefix("Bearer ").strip())
    except AuthenticationError:
        return None


OptionalCurrentUser = Annotated[User | None, Depends(get_optional_current_user)]
