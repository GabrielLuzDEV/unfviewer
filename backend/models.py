import re

from pydantic import BaseModel, field_validator

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9._]{1,30}$")


def _validate_username(v: str) -> str:
    v = v.strip().lstrip("@")
    if not _USERNAME_RE.match(v):
        raise ValueError("Nome de usuário inválido.")
    return v


class LoginRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        return _validate_username(v)

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        if not 1 <= len(v) <= 128:
            raise ValueError("Senha inválida.")
        return v


class CookieLoginRequest(BaseModel):
    username: str
    sessionid: str

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        return _validate_username(v)

    @field_validator("sessionid")
    @classmethod
    def check_sessionid(cls, v: str) -> str:
        v = v.strip()
        if not 10 <= len(v) <= 256:
            raise ValueError("Session ID inválido.")
        return v


class TwoFactorRequest(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def check_code(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"\d{6}", v):
            raise ValueError("Código 2FA deve ter 6 dígitos.")
        return v


class UnfollowRequest(BaseModel):
    username: str

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        return _validate_username(v)


class NonFollower(BaseModel):
    username: str
    followers: int
    profile_pic_url: str | None = None
    is_verified: bool = False


class SessionInfo(BaseModel):
    username: str
    tier: str = "free"
    awaiting_2fa: bool = False
