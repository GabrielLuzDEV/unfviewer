"""Disk I/O: app config, unfollow progress checkpoint, profile follower-count cache."""

import json
import os
import time
from typing import Any

from config import CONFIG_FILE, PROFILE_CACHE_FILE, PROFILE_CACHE_TTL, PROGRESS_FILE


# ── App config ────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(data: dict) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── Unfollow progress checkpoint ─────────────────────────────────────────────

def save_progress(username: str, remaining: list[tuple[str, int]], unfollowed: list[str]) -> None:
    data = {
        "username": username,
        "remaining": remaining,
        "unfollowed_so_far": unfollowed,
    }
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n💾 Progresso salvo em '{PROGRESS_FILE}'.")
    print("   Execute o script novamente amanhã para continuar.")


def load_progress() -> dict | None:
    if not os.path.exists(PROGRESS_FILE):
        return None
    with open(PROGRESS_FILE) as f:
        return json.load(f)


def clear_progress() -> None:
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)


# ── Profile follower-count cache (24 h TTL) ───────────────────────────────────

def load_profile_cache() -> dict:
    if os.path.exists(PROFILE_CACHE_FILE):
        with open(PROFILE_CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_profile_cache(cache: dict) -> None:
    with open(PROFILE_CACHE_FILE, "w") as f:
        json.dump(cache, f)


def cache_get(cache: dict, username: str) -> int | None:
    """Return cached follower count if within TTL, else None."""
    entry = cache.get(username)
    if entry and time.time() - entry["ts"] < PROFILE_CACHE_TTL:
        return entry["count"]
    return None


def cache_set(cache: dict, username: str, count: int) -> None:
    cache[username] = {"count": count, "ts": time.time()}
