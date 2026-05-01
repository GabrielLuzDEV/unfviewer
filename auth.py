"""Authentication: keyring helpers, session restore, fresh login, 2FA, browser-cookie fallback."""

import getpass
import os
import sys
import time

import instaloader

from config import _KEYRING_SERVICE

try:
    import keyring as _keyring_mod
    _backend = _keyring_mod.get_keyring()
    # Fail backend is keyring.backends.fail.Keyring — must check __module__ not just __name__
    _backend_id = f"{type(_backend).__module__}.{type(_backend).__name__}".lower()
    _KEYRING_OK = (
        "fail" not in _backend_id
        and "plaintext" not in _backend_id
        and "null" not in _backend_id
    )
except Exception:
    _keyring_mod = None  # type: ignore
    _KEYRING_OK = False


# ── Keyring helpers ───────────────────────────────────────────────────────────

def load_password(username: str) -> str | None:
    if not _KEYRING_OK or _keyring_mod is None:
        return None
    return _keyring_mod.get_password(_KEYRING_SERVICE, username)


def store_password(username: str, password: str) -> None:
    if _KEYRING_OK and _keyring_mod is not None:
        _keyring_mod.set_password(_KEYRING_SERVICE, username, password)


def delete_password(username: str) -> None:
    if _KEYRING_OK and _keyring_mod is not None:
        try:
            _keyring_mod.delete_password(_KEYRING_SERVICE, username)
        except Exception:
            pass


# ── 2FA helpers ───────────────────────────────────────────────────────────────

def _do_two_factor_login(loader: instaloader.Instaloader) -> bool:
    """Returns True on success, False if user wants browser-cookie fallback."""
    print("   🔑 Autenticação de dois fatores ativada.")
    print("   (deixe em branco para usar cookies do navegador como alternativa)")
    while True:
        codigo = input("   Código 2FA (6 dígitos): ").strip().replace(" ", "")
        if not codigo:
            return False
        authenticated = False
        for attempt in range(1, 4):
            try:
                loader.two_factor_login(codigo)
                authenticated = True
                break
            except instaloader.exceptions.BadCredentialsException:
                if attempt < 3:
                    print(f"   ⏳ Tentativa {attempt}/3 falhou, tentando novamente em 5s...")
                    time.sleep(5)
                else:
                    print("   ❌ Código rejeitado 3 vezes.")
                    print("   Tente outro código ou pressione Enter para usar cookies do navegador.")
            except Exception as exc:
                print(f"   ⚠️  Erro: {exc}")
                print("   Tente outro código ou pressione Enter para usar cookies do navegador.")
                break
        if authenticated:
            return True


def _login_with_browser_cookies(username: str, loader: instaloader.Instaloader) -> bool:
    print("\n   🌐 Login via cookies do navegador:")
    print("   1. Abra instagram.com no navegador (já logado)")
    print("   2. F12 → Application → Cookies → https://www.instagram.com")
    print("   3. Copie os valores de 'sessionid' e 'csrftoken'")
    sessionid = input("   sessionid: ").strip()
    if not sessionid:
        return False
    csrftoken = input("   csrftoken: ").strip()
    if not csrftoken:
        return False

    loader.context._session.cookies.update({"sessionid": sessionid, "csrftoken": csrftoken})
    loader.context._session.headers.update({"X-CSRFToken": csrftoken})
    loader.context.username = username
    return True


# ── Main login entry point ────────────────────────────────────────────────────

def login(username: str) -> tuple[instaloader.Instaloader, instaloader.Profile]:
    L = instaloader.Instaloader(
        sleep=True,
        quiet=False,
        user_agent=None,
        max_connection_attempts=3,
    )
    session_file = f".session_{username}"

    if os.path.exists(session_file):
        print(f"\n🔐 Restaurando sessão salva para @{username}...")
        try:
            L.load_session_from_file(username, session_file)
            profile = instaloader.Profile.from_username(L.context, username)
            print(f"   ✅ Sessão restaurada. Você segue {profile.followees} contas.\n")
            return L, profile
        except Exception:
            print("   ⚠️  Sessão expirada, fazendo login novamente...")

    print(f"\n🔐 Fazendo login como @{username}...")
    print("   🔒 Sua senha é enviada diretamente ao Instagram e descartada")
    print("      imediatamente após o login. Nunca é armazenada por este app.")

    if not _KEYRING_OK:
        print("   ℹ️  Keyring seguro não disponível (WSL2 sem D-Bus). Senha não será armazenada.")

    senha = load_password(username)
    if senha:
        print("   🔑 Usando senha armazenada no keyring do sistema.")
    else:
        senha = getpass.getpass("   Senha: ")

    try:
        L.login(username, senha)
    except instaloader.exceptions.BadCredentialsException:
        delete_password(username)
        print("   ❌ Senha incorreta. Tente novamente.")
        senha = getpass.getpass("   Senha: ")
        L.login(username, senha)
    except instaloader.exceptions.TwoFactorAuthRequiredException:
        if not _do_two_factor_login(L):
            if not _login_with_browser_cookies(username, L):
                print("❌ Autenticação cancelada.")
                sys.exit(1)

    if _KEYRING_OK and not load_password(username):
        guardar = input("   Salvar senha no keyring do sistema? [y/N]: ").strip().lower()
        if guardar == "y":
            store_password(username, senha)
            print("   💾 Senha armazenada com segurança no keyring.")

    L.save_session_to_file(session_file)
    print(f"   💾 Sessão salva em '{session_file}' (próximo login será automático).")

    profile = instaloader.Profile.from_username(L.context, username)
    print(f"   ✅ Logado. Você segue {profile.followees} contas.\n")
    return L, profile
