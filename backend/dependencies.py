"""Shared FastAPI dependencies."""

from fastapi import Cookie, HTTPException

from backend.session_store import Session, get_session


def get_current_session(sid: str | None = Cookie(default=None)) -> Session:
    """Resolve and return an authenticated session from the httpOnly sid cookie."""
    if not sid:
        raise HTTPException(status_code=401, detail="Sessão expirada. Faça login novamente.")
    s = get_session(sid)
    if not s:
        raise HTTPException(status_code=401, detail="Sessão expirada. Faça login novamente.")
    if s.awaiting_2fa:
        raise HTTPException(status_code=401, detail="Autenticação de dois fatores pendente.")
    return s
