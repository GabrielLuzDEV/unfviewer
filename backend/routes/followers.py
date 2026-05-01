"""Followers routes: fetch following/followers and stream progress via SSE."""

import asyncio
import json
import logging
import os
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from backend.dependencies import get_current_session
from backend.session_store import Session
from core_live import fetch_followees, fetch_followers
from core import compute_non_followers

log = logging.getLogger(__name__)

router = APIRouter(prefix="/followers", tags=["followers"])

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SNAPSHOT_FILE = _REPO_ROOT / "dev_snapshot.json"
_DEV_MODE = os.getenv("DEV_SNAPSHOT", "").strip() == "1"


async def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _load_snapshot() -> list[dict]:
    with open(_SNAPSHOT_FILE) as f:
        data = json.load(f)
    return [
        {"username": u, "followers": 0, "profile_pic_url": None, "is_verified": False}
        for u in data["non_followers"]
    ]


def _safe_message(msg: str) -> str:
    """Strip stack traces and internal paths from messages forwarded to the client."""
    if "Traceback" in msg or "File /" in msg:
        return "Erro ao se comunicar com o Instagram. Tente novamente."
    return msg[:500]


@router.get("/non-followers/stream")
async def stream_non_followers(request: Request, s: Session = Depends(get_current_session)):
    """Server-Sent Events stream with progress updates then the final non-follower list."""
    if s.non_followers and not s.fetch_in_progress:
        async def _cached():
            yield await _sse_event({
                "type": "done",
                "count": len(s.non_followers),
                "non_followers": s.non_followers,
                "partial": False,
            })
        return StreamingResponse(_cached(), media_type="text/event-stream")

    if s.fetch_in_progress:
        async def _busy():
            yield await _sse_event({
                "type": "busy",
                "message": "Uma busca já está em andamento.",
                "retry_after": 3,
            })
        return StreamingResponse(_busy(), media_type="text/event-stream")

    stop_event = threading.Event()
    s.fetch_stop_event = stop_event
    s.fetch_in_progress = True

    async def generate():
        loop = asyncio.get_event_loop()
        warnings: list[str] = []

        try:
            if _DEV_MODE and _SNAPSHOT_FILE.exists():
                yield await _sse_event({"type": "progress", "message": "[DEV] Carregando snapshot local..."})
                await asyncio.sleep(0.5)
                non_followers_list = _load_snapshot()
                s.non_followers = non_followers_list
                yield await _sse_event({
                    "type": "done",
                    "count": len(non_followers_list),
                    "non_followers": non_followers_list,
                    "partial": False,
                })
                return

            # ── Phase 1: followees (skip if already cached) ───────────────────
            if s.followees_cache is not None:
                followees = s.followees_cache
                yield await _sse_event({
                    "type": "progress",
                    "message": f"Retomando busca — {len(followees)} contas seguidas já carregadas.",
                })
            else:
                yield await _sse_event({"type": "progress", "message": "Buscando contas que você segue..."})
                try:
                    followees, w1 = await loop.run_in_executor(
                        None, fetch_followees, s.client, s.user_id, stop_event
                    )
                except Exception:
                    log.error("[stream] unexpected error in phase 1", exc_info=True)
                    yield await _sse_event({"type": "error", "message": "Erro interno. Tente novamente."})
                    return

                if stop_event.is_set():
                    return

                warnings.extend(w1)
                s.followees_cache = followees

            # ── Phase 2: followers ────────────────────────────────────────────
            yield await _sse_event({"type": "progress", "message": "Buscando seus seguidores..."})
            try:
                followers, w2 = await loop.run_in_executor(
                    None, fetch_followers, s.client, s.user_id, stop_event
                )
            except Exception:
                log.error("[stream] unexpected error in phase 2", exc_info=True)
                yield await _sse_event({"type": "error", "message": "Erro interno. Tente novamente."})
                return

            if stop_event.is_set():
                return

            warnings.extend(w2)

            if len(followees) == 0 and len(followers) == 0 and warnings:
                yield await _sse_event({
                    "type": "error",
                    "message": "Instagram bloqueou todas as tentativas de busca. Aguarde 15–30 minutos e tente novamente.",
                })
                return

            for warning in warnings:
                yield await _sse_event({"type": "warning", "message": _safe_message(warning)})

            dont_follow_back = compute_non_followers(followees, followers)
            non_followers_list = [
                {"username": u, "followers": 0, "profile_pic_url": None, "is_verified": False}
                for u in sorted(dont_follow_back)
            ]
            s.non_followers = non_followers_list
            s.followees_cache = None

            yield await _sse_event({
                "type": "done",
                "count": len(non_followers_list),
                "non_followers": non_followers_list,
                "partial": len(warnings) > 0,
            })

        finally:
            s.fetch_in_progress = False
            stop_event.set()

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/non-followers")
async def get_non_followers(s: Session = Depends(get_current_session)):
    return {"non_followers": s.non_followers, "count": len(s.non_followers)}
