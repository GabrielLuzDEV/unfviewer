"""
Instagram Non-Follower Finder & Selective Unfollower
=====================================================
Entry point shim. All logic lives in the module files:

  config.py       — constants (caps, delays, file paths)
  storage.py      — disk I/O (config, progress, profile cache)
  auth.py         — login, keyring, 2FA, browser-cookie fallback
  core.py         — pure computation (non-follower diff, sort)
  core_live.py    — live instaloader: fetch lists, follower counts, unfollow
  core_export.py  — free-tier: parse Instagram data export ZIP
  cli.py          — interactive CLI loop and main()

USAGE:
    python instagram_unfollower.py
"""

import instaloader

from cli import main

if __name__ == "__main__":
    try:
        main()
    except instaloader.exceptions.ConnectionException as e:
        print(f"\n🛑 Erro de conexão com o Instagram: {e}")
        print("   Aguarde alguns minutos e tente novamente.")
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\n\n👋 Interrompido pelo usuário.")
        raise SystemExit(0)
