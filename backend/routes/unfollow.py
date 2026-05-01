"""Unfollow route: server-enforced rate limiting, free-tier gate."""

import asyncio
import logging
import random
import time

from fastapi import APIRouter, Depends, HTTPException, Path

from instagrapi.exceptions import ClientError

from backend.dependencies import get_current_session
from backend.session_store import Session
from config import (
    FREE_UNFOLLOW_LIMIT,
    MAX_UNFOLLOWS_PER_SESSION,
    UNFOLLOW_COOLDOWN_EVERY,
    UNFOLLOW_COOLDOWN_SEC,
    UNFOLLOW_DELAY_MAX,
    UNFOLLOW_DELAY_MIN,
)
from core_live import unfollow_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/unfollow", tags=["unfollow"])


@router.post("/{username}")
async def do_unfollow(
    username: str = Path(..., pattern=r"^[a-zA-Z0-9._]{1,30}$"),
    s: Session = Depends(get_current_session),
):
    cap = FREE_UNFOLLOW_LIMIT if s.tier == "free" else MAX_UNFOLLOWS_PER_SESSION
    if len(s.unfollowed_session) >= cap:
        raise HTTPException(
            status_code=402,
            detail=(
                "Limite do plano gratuito atingido. Assine o Premium para desbloquear mais unfollows."
                if s.tier == "free"
                else f"Cap de {MAX_UNFOLLOWS_PER_SESSION} unfollows atingido."
            ),
        )

    # ── Cooldown gate: 5-minute pause every UNFOLLOW_COOLDOWN_EVERY unfollows ──
    if s.unfollow_batch_count >= UNFOLLOW_COOLDOWN_EVERY:
        elapsed = time.time() - s.last_unfollow_at
        remaining = int(UNFOLLOW_COOLDOWN_SEC - elapsed)
        if remaining > 0:
            raise HTTPException(
                status_code=429,
                detail="Pausa de segurança ativa.",
                headers={"Retry-After": str(remaining), "X-Cooldown-Remaining": str(remaining)},
            )
        # cooldown expired — reset the batch counter
        s.unfollow_batch_count = 0

    # ── Human-paced delay before the actual unfollow call ──────────────────────
    delay = random.uniform(UNFOLLOW_DELAY_MIN, UNFOLLOW_DELAY_MAX)
    log.info("[unfollow] waiting %.1fs before unfollowing @%s", delay, username)
    await asyncio.sleep(delay)

    try:
        unfollow_user(s.client, username)
        s.unfollowed_session.append(username)
        s.unfollow_batch_count += 1
        s.last_unfollow_at = time.time()
    except ClientError as e:
        if "429" in str(e) or "throttled" in str(e).lower():
            raise HTTPException(status_code=429, detail="Instagram bloqueou. Aguarde 24–48h.")
        log.error("[unfollow] ClientError for @%s: %s", username, e)
        raise HTTPException(status_code=500, detail="Erro interno. Tente novamente.")
    except Exception:
        log.error("[unfollow] unexpected error for @%s", username, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno. Tente novamente.")

    unfollowed_count = len(s.unfollowed_session)
    next_cooldown_in = UNFOLLOW_COOLDOWN_EVERY - s.unfollow_batch_count

    return {
        "ok": True,
        "username": username,
        "unfollowed_count": unfollowed_count,
        "cap": cap,
        "tier": s.tier,
        "next_cooldown_in": next_cooldown_in,  # unfollows until next 5-min pause
    }

# NOTE: rewarded-unlock endpoint removed — had no server-side ad verification.
# Re-implement only after integrating a real ad SDK with signed server-side callbacks.
