"""Auth routes: login, 2FA, logout."""

import logging
import os
import traceback

from fastapi import APIRouter, Cookie, HTTPException, Request, Response

from instagrapi.exceptions import (
    BadPassword,
    CaptchaChallengeRequired,
    ChallengeRequired,
    LoginRequired,
    RecaptchaChallengeForm,
    TwoFactorRequired,
    UnknownError,
)

from backend.middleware.rate_limit import limiter
from backend.models import CookieLoginRequest, LoginRequest, SessionInfo, TwoFactorRequest
from core_live import _make_client
from backend.session_store import (
    Session,
    clear_pending_password,
    create_session,
    delete_session,
    get_pending_password,
    get_session,
    load_session_file,
    save_session_file,
    set_pending_password,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
_COOKIE_SAMESITE = "none" if _COOKIE_SECURE else "lax"
_SESSION_TTL = 28_800


def _set_session_cookie(response: Response, sid: str) -> None:
    response.set_cookie(
        key="sid",
        value=sid,
        httponly=True,
        samesite=_COOKIE_SAMESITE,
        secure=_COOKIE_SECURE,
        max_age=_SESSION_TTL,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key="sid", path="/", samesite=_COOKIE_SAMESITE)


@router.post("/login", response_model=SessionInfo)
@limiter.limit("5/minute")
async def login(request: Request, req: LoginRequest, response: Response):
    log.info("[login] attempt for %s", req.username)

    existing = load_session_file(req.username)
    if existing is not None:
        log.info("[login] reusing session file for %s", req.username)
        sid = create_session(req.username, existing)
        s = get_session(sid)
        s.user_id = existing.user_id
        _set_session_cookie(response, sid)
        return SessionInfo(username=req.username, tier="free")

    log.info("[login] fresh password login for %s", req.username)
    cl = _make_client()

    try:
        cl.login(req.username, req.password)
        log.info("[login] succeeded  user_id=%s", cl.user_id)
    except TwoFactorRequired:
        log.info("[login] 2FA required for %s", req.username)
        sid = create_session(req.username, cl)
        s = get_session(sid)
        s.awaiting_2fa = True
        set_pending_password(s, req.password)
        _set_session_cookie(response, sid)
        return SessionInfo(username=req.username, tier="free", awaiting_2fa=True)
    except BadPassword as e:
        log.warning("[login] bad password for %s: %s", req.username, e)
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos.")
    except (ChallengeRequired, CaptchaChallengeRequired, RecaptchaChallengeForm) as e:
        log.warning("[login] challenge for %s: %s", req.username, type(e).__name__)
        raise HTTPException(
            status_code=401,
            detail=(
                "Instagram solicitou verificação adicional. "
                "Faça login em instagram.com, complete a verificação e tente novamente."
            ),
        )
    except LoginRequired as e:
        log.warning("[login] login required for %s: %s", req.username, e)
        raise HTTPException(
            status_code=401,
            detail="Instagram bloqueou o login automático. Tente novamente em alguns minutos.",
        )
    except UnknownError as e:
        log.warning("[login] unknown Instagram error for %s: %s", req.username, e)
        raise HTTPException(
            status_code=401,
            detail="Instagram retornou um erro desconhecido. Tente novamente.",
        )
    except Exception:
        log.error("[login] unexpected error for %s:\n%s", req.username, traceback.format_exc())
        raise HTTPException(status_code=500, detail="Erro interno. Tente novamente.")

    save_session_file(cl, req.username)
    sid = create_session(req.username, cl)
    s = get_session(sid)
    s.user_id = cl.user_id
    _set_session_cookie(response, sid)
    return SessionInfo(username=req.username, tier="free")


@router.post("/2fa", response_model=SessionInfo)
@limiter.limit("5/minute")
async def two_factor(request: Request, req: TwoFactorRequest, response: Response, sid: str | None = Cookie(default=None)):
    if not sid:
        raise HTTPException(status_code=400, detail="Sessão inválida ou 2FA não pendente.")
    s = get_session(sid)
    if not s or not s.awaiting_2fa:
        raise HTTPException(status_code=400, detail="Sessão inválida ou 2FA não pendente.")

    try:
        password = get_pending_password(s)
        s.client.login(s.username, password, verification_code=req.code)
    except BadPassword:
        raise HTTPException(status_code=401, detail="Código 2FA incorreto.")
    except Exception:
        log.error("[2fa] unexpected error for %s:\n%s", s.username, traceback.format_exc())
        raise HTTPException(status_code=500, detail="Erro interno. Tente novamente.")

    s.awaiting_2fa = False
    clear_pending_password(s)
    s.user_id = s.client.user_id
    save_session_file(s.client, s.username)
    _set_session_cookie(response, sid)
    return SessionInfo(username=s.username, tier=s.tier)


@router.post("/login-cookie", response_model=SessionInfo)
@limiter.limit("5/minute")
async def login_cookie(request: Request, req: CookieLoginRequest, response: Response):
    log.info("[login-cookie] attempt for %s", req.username)
    cl = _make_client()
    try:
        cl.login_by_sessionid(req.sessionid)
        log.info("[login-cookie] succeeded  user_id=%s  username=%s", cl.user_id, cl.username)
    except AssertionError:
        raise HTTPException(
            status_code=400,
            detail="Session ID inválido. Copie o valor completo do cookie sessionid.",
        )
    except Exception:
        log.warning("[login-cookie] failed for %s:\n%s", req.username, traceback.format_exc())
        raise HTTPException(
            status_code=401,
            detail="Não foi possível autenticar com esse session ID. Verifique se está logado em instagram.com.",
        )

    save_session_file(cl, cl.username)
    sid = create_session(cl.username, cl)
    s = get_session(sid)
    s.user_id = cl.user_id
    _set_session_cookie(response, sid)
    return SessionInfo(username=cl.username, tier="free")


@router.get("/validate", response_model=SessionInfo)
async def validate_session(sid: str | None = Cookie(default=None)):
    if not sid:
        raise HTTPException(status_code=401, detail="Não autenticado.")
    s = get_session(sid)
    if not s or s.awaiting_2fa:
        raise HTTPException(status_code=401, detail="Sessão inválida.")
    return SessionInfo(username=s.username, tier=s.tier)


@router.post("/logout")
async def logout(response: Response, sid: str | None = Cookie(default=None)):
    if sid:
        s = get_session(sid)
        if s:
            log.info("[logout] %s", s.username)
        delete_session(sid)
    _clear_session_cookie(response)
    return {"ok": True}
