"""In-memory session store with encrypted on-disk persistence."""

import base64
import json
import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from instagrapi import Client

log = logging.getLogger(__name__)

SESSION_TTL = 28_800      # 8 hours
PENDING_2FA_TTL = 300     # 5 minutes for 2FA window

_sessions: dict[str, "Session"] = {}

_SESSIONS_DIR = Path(__file__).resolve().parent / ".sessions"
_SESSIONS_DIR.mkdir(mode=0o700, exist_ok=True)

_fernet_cache: Fernet | None = None
_DEV_FALLBACK_KEY = "unfviewer-dev-only-not-for-production-1234"


def _get_fernet() -> Fernet:
    global _fernet_cache
    if _fernet_cache is not None:
        return _fernet_cache
    raw_key = os.environ.get("SECRET_KEY", _DEV_FALLBACK_KEY)
    if raw_key == "change-me-in-production":
        raw_key = _DEV_FALLBACK_KEY
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"unfviewer-session-v1",
        iterations=100_000,
    )
    derived = base64.urlsafe_b64encode(kdf.derive(raw_key.encode()))
    _fernet_cache = Fernet(derived)
    return _fernet_cache


@dataclass
class Session:
    username: str
    client: Client
    tier: str = "free"
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    non_followers: list[dict] = field(default_factory=list)
    unfollowed_session: list[str] = field(default_factory=list)
    awaiting_2fa: bool = False
    _enc_password: bytes = field(default=b"")   # encrypted; cleared after 2FA
    user_id: int | None = None
    followees_cache: dict | None = None
    fetch_stop_event: threading.Event | None = None
    fetch_in_progress: bool = False
    # Unfollow rate limiting
    last_unfollow_at: float = 0.0
    unfollow_batch_count: int = 0   # resets after cooldown pause


def create_session(username: str, client: Client, tier: str = "free") -> str:
    sid = secrets.token_urlsafe(32)
    _sessions[sid] = Session(username=username, client=client, tier=tier)
    return sid


def get_session(sid: str) -> Session | None:
    s = _sessions.get(sid)
    if s is None:
        return None
    if time.time() - s.last_used > SESSION_TTL:
        del _sessions[sid]
        return None
    s.last_used = time.time()
    return s


def delete_session(sid: str) -> None:
    s = _sessions.pop(sid, None)
    if s:
        _delete_session_file(s.username)


def set_pending_password(session: Session, password: str) -> None:
    session._enc_password = _get_fernet().encrypt(password.encode())


def get_pending_password(session: Session) -> str:
    if not session._enc_password:
        raise ValueError("no pending password stored in session")
    return _get_fernet().decrypt(session._enc_password).decode()


def clear_pending_password(session: Session) -> None:
    session._enc_password = b""


# ── On-disk session file helpers ──────────────────────────────────────────────

def _session_file(username: str) -> Path:
    return _SESSIONS_DIR / f"{username}.enc"


def save_session_file(cl: Client, username: str) -> None:
    try:
        plaintext = json.dumps(cl.get_settings()).encode()
        encrypted = _get_fernet().encrypt(plaintext)
        _session_file(username).write_bytes(encrypted)
    except Exception as e:
        log.warning("[session] failed to save session file for %s: %s", username, e)


def load_session_file(username: str) -> Client | None:
    path = _session_file(username)
    if not path.exists():
        return None
    try:
        encrypted = path.read_bytes()
        plaintext = _get_fernet().decrypt(encrypted)
        settings = json.loads(plaintext.decode())
        cl = Client()
        cl.set_settings(settings)
        if not cl.user_id:
            raise ValueError("no user_id in saved settings")
        log.info("[session] reused session file for %s  user_id=%s", username, cl.user_id)
        return cl
    except (InvalidToken, Exception) as e:
        log.warning("[session] session file invalid for %s: %s — deleting", username, e)
        _delete_session_file(username)
        return None


def _delete_session_file(username: str) -> None:
    try:
        _session_file(username).unlink(missing_ok=True)
    except Exception:
        pass


# ── Background eviction ───────────────────────────────────────────────────────

def _evict_expired() -> None:
    now = time.time()
    expired = [sid for sid, s in list(_sessions.items()) if now - s.last_used > SESSION_TTL]
    for sid in expired:
        _sessions.pop(sid, None)
