"""CLI entry point: display, interactive unfollow loop, and main()."""

import random
import sys
import time

import instaloader

from auth import login
from config import (
    CONFIG_FILE,
    FETCH_DELAY_MIN,
    FREE_UNFOLLOW_LIMIT,
    MAX_UNFOLLOWS_PER_SESSION,
    UNFOLLOW_DELAY_MAX,
    UNFOLLOW_DELAY_MIN,
)
from core import compute_non_followers, sort_by_followers
from core_live import get_follower_counts, get_following_and_followers, unfollow_user
from storage import clear_progress, load_config, load_progress, save_config, save_progress


def display_non_followers(non_followers: list[tuple[str, int]]) -> None:
    print("\n" + "═" * 60)
    print(f"  👻  {len(non_followers)} contas que NÃO seguem você de volta")
    print("═" * 60)
    print(f"  {'#':>4}  {'Username':<30}  {'Seguidores':>10}")
    print("─" * 60)
    for i, (username, count) in enumerate(non_followers, 1):
        seg_str = f"{count:,}" if count >= 0 else "N/A"
        print(f"  {i:>4}  @{username:<29}  {seg_str:>10}")
    print("═" * 60)


def interactive_unfollow(
    L: instaloader.Instaloader,
    non_followers: list[tuple[str, int]],
    my_username: str,
    profile_cache: dict[str, instaloader.Profile] | None = None,
    free_tier: bool = False,
) -> None:
    """
    y = unfollow | n = skip | q = quit | p = pause & save

    profile_cache: username→Profile from get_following_and_followers(),
    avoids a redundant Profile.from_username() call per unfollow.

    free_tier: caps at FREE_UNFOLLOW_LIMIT and prompts rewarded-ad gate.
    """
    unfollowed_session: list[str] = []
    total = len(non_followers)
    session_cap = FREE_UNFOLLOW_LIMIT if free_tier else MAX_UNFOLLOWS_PER_SESSION

    print(f"\n{'═' * 60}")
    print(f"  🎯  Modo interativo — {total} conta(s) para revisar")
    if free_tier:
        print(f"  ℹ️  Plano gratuito: {FREE_UNFOLLOW_LIMIT} unfollows por sessão")
    print("  y = deixar de seguir  |  n = manter  |  q = sair  |  p = pausar")
    print(f"{'═' * 60}\n")

    i = 0
    while i < total:
        username, count = non_followers[i]
        seg_str = f"{count:,}" if count >= 0 else "N/A"

        print(f"  [{i + 1}/{total}]  @{username}  ({seg_str} seguidores)")
        print(f"          🔗 https://www.instagram.com/{username}/")

        while True:
            cmd = input("          Deixar de seguir? [y/n/q/p]: ").strip().lower()
            if cmd in ("y", "n", "q", "p"):
                break
            print("          ⚠️  Digite y, n, q ou p.")

        if cmd == "q":
            print("\n👋 Saindo sem salvar progresso.")
            break

        if cmd == "p":
            save_progress(my_username, non_followers[i:], unfollowed_session)
            break

        if cmd == "n":
            print(f"          ↩️  Mantendo @{username}.\n")
            i += 1
            continue

        # ── Cap check ─────────────────────────────────────────────────────────
        if len(unfollowed_session) >= session_cap:
            if free_tier:
                print(f"\n  🔒  Limite do plano gratuito ({FREE_UNFOLLOW_LIMIT} unfollows) atingido.")
                print("      Assine o Premium para continuar sem limites, ou assista")
                print("      um vídeo recompensado para desbloquear +10 unfollows.")
            else:
                print(f"\n  ⛔  Cap de {MAX_UNFOLLOWS_PER_SESSION} unfollows atingido nesta sessão.")
                print("      Salve o progresso e retome amanhã.")
            save_progress(my_username, non_followers[i:], unfollowed_session)
            break

        try:
            profile_obj = (
                profile_cache[username]
                if profile_cache and username in profile_cache
                else instaloader.Profile.from_username(L.context, username)
            )
            unfollow_user(L, profile_obj)
            unfollowed_session.append(username)
            used = len(unfollowed_session)
            print(f"          ✅ Deixou de seguir @{username}  ({used}/{session_cap} nesta sessão)\n")

        except instaloader.exceptions.TooManyRequestsException:
            print(f"\n  🛑 Instagram bloqueou após {len(unfollowed_session)} unfollows.")
            print("     Aguarde 24–48h antes de tentar novamente.")
            save_progress(my_username, non_followers[i:], unfollowed_session)
            break

        except Exception as e:
            print(f"          ⚠️  Erro ao deixar de seguir @{username}: {e}\n")
            i += 1
            continue

        i += 1

        if i < total and cmd == "y":
            delay = random.uniform(UNFOLLOW_DELAY_MIN, UNFOLLOW_DELAY_MAX)
            print(f"          ⏳ Aguardando {delay:.0f}s antes do próximo...\n")
            time.sleep(delay)

    print(f"\n{'═' * 60}")
    print("  📊  Resumo da sessão")
    print(f"{'─' * 60}")
    print(f"  ✅ Deixou de seguir: {len(unfollowed_session)} conta(s)")
    for u in unfollowed_session:
        print(f"      • @{u}")
    print("\n  ⚠️  Limite seguro: ~100–150 unfollows/dia no total.")
    print(f"{'═' * 60}\n")


def main() -> None:
    print("╔══════════════════════════════════════════════╗")
    print("║   Instagram Non-Follower Finder v2.0         ║")
    print("║   Modo interativo y/n por conta              ║")
    print("╚══════════════════════════════════════════════╝")

    # ── Resume saved progress ─────────────────────────────────────────────────
    progress = load_progress()
    if progress:
        saved_user = progress["username"]
        print(f"\n💾 Progresso anterior encontrado para @{saved_user}.")
        print(f"   {len(progress['remaining'])} conta(s) pendentes de revisão.")
        retomar = input("   Retomar de onde parou? [Y/n]: ").strip().lower()
        if retomar != "n":
            L, _ = login(saved_user)
            non_followers = [tuple(x) for x in progress["remaining"]]
            clear_progress()
            interactive_unfollow(L, non_followers, saved_user)
            return

    # ── Normal flow ───────────────────────────────────────────────────────────
    config = load_config()
    username = config.get("username", "").strip().lstrip("@")
    if not username:
        username = input("\nSeu usuário do Instagram: ").strip().lstrip("@")
        if not username:
            print("❌ Nenhum usuário informado. Saindo.")
            sys.exit(1)
        config["username"] = username
        save_config(config)
        print(f"   💾 Usuário salvo em '{CONFIG_FILE}' para próximas execuções.")
    else:
        print(f"\n👤 Usando conta salva: @{username}  (edite '{CONFIG_FILE}' para trocar)")

    L, profile = login(username)
    followees, followers, _warnings = get_following_and_followers(profile)

    dont_follow_back = compute_non_followers(followees, followers)
    print(f"🔍 {len(dont_follow_back)} contas não seguem você de volta.\n")

    if not dont_follow_back:
        print("🎉 Todos que você segue também seguem você de volta!")
        sys.exit(0)

    resp = input(
        f"Buscar contagem de seguidores das {len(dont_follow_back)} contas? "
        f"(~{len(dont_follow_back) * FETCH_DELAY_MIN // 3}s a mais) [Y/n]: "
    ).strip().lower()

    counts = (
        get_follower_counts(L, list(dont_follow_back))
        if resp != "n"
        else dict.fromkeys(dont_follow_back, 0)
    )

    sorted_non_followers = sort_by_followers(dont_follow_back, counts)
    display_non_followers(sorted_non_followers)

    profile_cache = {u: followees[u] for u in dont_follow_back}

    print("\n")
    interactive_unfollow(L, sorted_non_followers, username, profile_cache=profile_cache)
