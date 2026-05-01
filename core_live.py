"""Live Instagram operations via instagrapi (mobile private API)."""

import logging
import os
import threading
import time

from instagrapi import Client
from instagrapi.exceptions import ClientError, LoginRequired, PleaseWaitFewMinutes

from config import FETCH_PAGE_DELAY_MAX, FETCH_PAGE_DELAY_MIN

log = logging.getLogger(__name__)


def _make_client() -> Client:
    """Create an instagrapi Client with delay_range and optional proxy configured."""
    cl = Client()
    # Random inter-request delay — instagrapi applies this automatically between
    # every private API call, mimicking human browsing cadence.
    cl.delay_range = [FETCH_PAGE_DELAY_MIN, FETCH_PAGE_DELAY_MAX]
    if proxy := os.environ.get("INSTAGRAM_PROXY"):
        cl.set_proxy(proxy)
        log.info("[client] proxy configured: %s", proxy.split("@")[-1])
    return cl


def fetch_followees(
    client: Client,
    user_id: int,
    stop_event: threading.Event | None = None,
) -> tuple[dict, list[str]]:
    """Fetch accounts the user follows.

    Returns (followees dict username→UserShort, warnings list).
    instagrapi's delay_range handles inter-page delays automatically.
    """
    warnings: list[str] = []
    log.info("[fetch] fetching followees for user_id=%s", user_id)
    try:
        raw = client.user_following_v1(user_id, amount=0)
        followees = {u.username: u for u in raw.values()}
        log.info("[fetch] %d followees fetched", len(followees))
        return followees, warnings
    except PleaseWaitFewMinutes:
        warnings.append(
            "Instagram pediu para aguardar alguns minutos. "
            "Tente novamente em 15–30 minutos."
        )
        return {}, warnings
    except (LoginRequired, ClientError) as e:
        warnings.append(f"Erro ao buscar contas seguidas: {e}")
        return {}, warnings
    except Exception as e:
        warnings.append(f"Erro inesperado ao buscar contas seguidas: {e}")
        return {}, warnings


def fetch_followers(
    client: Client,
    user_id: int,
    stop_event: threading.Event | None = None,
) -> tuple[set[str], list[str]]:
    """Fetch accounts that follow the user.

    Returns (followers set of usernames, warnings list).
    """
    warnings: list[str] = []
    log.info("[fetch] fetching followers for user_id=%s", user_id)
    try:
        raw = client.user_followers_v1(user_id, amount=0)
        followers = {u.username for u in raw.values()}
        log.info("[fetch] %d followers fetched", len(followers))
        return followers, warnings
    except PleaseWaitFewMinutes:
        warnings.append(
            "Instagram pediu para aguardar alguns minutos. "
            "Tente novamente em 15–30 minutos."
        )
        return set(), warnings
    except (LoginRequired, ClientError) as e:
        warnings.append(f"Erro ao buscar seguidores: {e}")
        return set(), warnings
    except Exception as e:
        warnings.append(f"Erro inesperado ao buscar seguidores: {e}")
        return set(), warnings


def get_follower_counts(
    client: Client,
    usernames: list[str],
) -> dict[str, int]:
    """Fetch follower counts for a list of usernames. Best-effort; slow."""
    counts: dict[str, int] = {}
    for username in usernames:
        try:
            user_id = client.user_id_from_username(username)
            info = client.user_info(user_id)
            counts[username] = info.follower_count
        except Exception:
            counts[username] = -1
    return counts


def unfollow_user(client: Client, username: str) -> None:
    """Unfollow a user by username."""
    user_id = client.user_id_from_username(username)
    client.user_unfollow(user_id)
