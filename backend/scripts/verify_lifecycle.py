"""Run a real, low-cost lifecycle check against a running local API."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from sqlalchemy import delete


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.models import Essay, User
from app.db.session import get_session_factory


async def verify(base_url: str) -> dict[str, object]:
    email = f"lifecycle-{uuid4().hex[:10]}@example.com"
    password = "Lifecycle-test-2026"
    user_id: UUID | None = None
    results: dict[str, object] = {}
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=45) as client:
            response = await client.post(
                "/api/auth/register",
                json={
                    "email": email,
                    "display_name": "生命周期测试",
                    "password": password,
                },
            )
            response.raise_for_status()
            session_payload = response.json()
            user_id = UUID(session_payload["user"]["id"])
            client.headers["Authorization"] = (
                f"Bearer {session_payload['access_token']}"
            )

            profile = await client.patch(
                "/api/auth/me",
                json={
                    "display_name": "生命周期测试",
                    "grade_level": "初二",
                    "default_genre": "记叙文",
                },
            )
            results["profile_settings"] = (
                profile.status_code == 200
                and profile.json().get("grade_level") == "初二"
            )

            first = await client.post(
                "/api/essays",
                data={
                    "title": "刷新前临时稿",
                    "original_text": "这是一次临时作文，用来验证刷新后不会恢复。",
                },
            )
            first.raise_for_status()
            first_id = first.json()["id"]
            history = await client.get("/api/essays")
            results["unfinished_hidden_from_history"] = (
                history.status_code == 200 and not history.json()["items"]
            )

            refreshed = await client.get("/api/auth/me")
            cleared = await client.get(f"/api/essays/{first_id}")
            results["refresh_session_clears_unfinished"] = (
                refreshed.status_code == 200 and cleared.status_code == 404
            )

            logout_draft = await client.post(
                "/api/essays",
                data={
                    "title": "退出前临时稿",
                    "original_text": "这篇临时作文用于验证退出和重新登录后的清理。",
                },
            )
            logout_draft.raise_for_status()
            logout_draft_id = logout_draft.json()["id"]
            logout_before_review = await client.post("/api/auth/logout")
            client.headers.pop("Authorization", None)
            login = await client.post(
                "/api/auth/login", json={"email": email, "password": password}
            )
            login.raise_for_status()
            client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
            discarded_after_login = await client.get(
                f"/api/essays/{logout_draft_id}"
            )
            results["logout_login_clears_unfinished"] = (
                logout_before_review.status_code == 204
                and discarded_after_login.status_code == 404
            )

            essay_text = (
                "放学后的天空很亮。我走到操场边，看见一片树叶落在跑道上。"
                "它被风推着向前，像一只慢慢航行的小船。我忽然想起今天没有解出的题，"
                "便停下来重新想了一遍。回到教室后，我终于找到了错误，"
                "也明白耐心比着急更有用。"
            )
            draft = await client.post(
                "/api/essays",
                data={
                    "title": "一片树叶",
                    "original_text": essay_text,
                    "grade_level": "初二",
                    "genre": "记叙文",
                },
            )
            draft.raise_for_status()
            essay_id = draft.json()["id"]
            still_there = await client.get(f"/api/essays/{essay_id}")
            history_during = await client.get("/api/essays")
            results["in_session_task_exists"] = (
                still_there.status_code == 200 and not history_during.json()["items"]
            )

            batch_response = await client.post(
                f"/api/essays/{essay_id}/reviews/batches",
                json={"providers": ["deepseek", "qwen", "doubao"]},
            )
            results["start_without_precheck"] = batch_response.status_code == 202
            if results["start_without_precheck"]:
                batch_id = batch_response.json()["id"]
                batch: dict[str, object] | None = None
                final: dict[str, object] | None = None
                for _ in range(100):
                    await asyncio.sleep(2)
                    poll = await client.get(
                        f"/api/essays/{essay_id}/reviews/batches"
                    )
                    poll.raise_for_status()
                    batches = poll.json()
                    batch = next(
                        (item for item in batches if item["id"] == batch_id),
                        batches[0] if batches else None,
                    )
                    if batch and batch["status"] in {"completed", "failed"}:
                        final = batch.get("final_evaluation")
                        break
                results["final_report"] = bool(
                    final
                    and isinstance(final.get("overall_score"), (int, float))
                    and final.get("summary")
                )
                results["polish_not_automatic"] = bool(final) and final.get("polish") is None
                results["completed_review_count"] = sum(
                    1
                    for item in (batch or {}).get("reviews", [])
                    if item.get("status") == "completed"
                )
                history_after = await client.get("/api/essays")
                results["history_only_after_success"] = bool(
                    results["final_report"]
                    and any(
                        item["id"] == essay_id
                        for item in history_after.json()["items"]
                    )
                )
            else:
                results["final_report"] = False
            results["elapsed_seconds"] = round(time.perf_counter() - started, 1)
            logout = await client.post("/api/auth/logout")
            results["logout"] = logout.status_code == 204
    finally:
        if user_id is not None:
            async with get_session_factory()() as session:
                await session.execute(delete(Essay).where(Essay.author_id == user_id))
                await session.execute(delete(User).where(User.id == user_id))
                await session.commit()
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(verify(args.base_url)), ensure_ascii=False))


if __name__ == "__main__":
    main()
