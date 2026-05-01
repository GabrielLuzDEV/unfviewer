

# Instagram Unfollower — Refactoring & Improvement Plan

**Target file:** `instagram_unfollower.py`
**Python:** 3.10+

---

## Product Pillars

**1. Confidentiality & Information Security — non-negotiable**
The user's Instagram password is sent directly to Instagram's servers and discarded from memory immediately after authentication. It is never logged, never stored on disk, never transmitted to our infrastructure. This guarantee must be communicated explicitly and proactively to the user at every login point — in the CLI, in the web UI, and in the landing page copy. The session token (not the password) is the only credential we persist, stored encrypted. If we ever compromise on this pillar, we compromise the entire product.

**2. Zero-friction UX — login once, everything appears**
The user's only required action is logging in with their Instagram credentials. Once authenticated, all features appear immediately — no setup steps, no configuration screens, no instructions to follow. The app figures out the rest. This applies equally to the website and the mobile app: login → features. Nothing in between.

**3. Live data advantage**
The premium instaloader flow provides real-time data — never stale — which is the core differentiator vs competitors that rely on Instagram's JSON export.

**4. User control**
Every unfollow is explicit and user-initiated, one account at a time. The app never takes automated action on the user's behalf without confirmation.

---

## Product Vision: Dual-Flow Architecture

The app supports two distinct flows gated by plan tier. Both flows share the same analysis logic (`core.py`) and UI layer — only the data source and write capabilities differ.

```
┌─────────────────────────────────────────────────────────┐
│                        FREE TIER                        │
│                                                         │
│  User downloads Instagram data export (JSON)            │
│       ↓                                                 │
│  App parses following.json + followers_1.json locally   │
│       ↓                                                 │
│  Computes non-followers list                            │
│       ↓                                                 │
│  Shows profiles (read-only)                             │
│       ↓                                                 │
│  Unfollow → opens instagram.com/<username> in browser   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                     PREMIUM TIER                        │
│                                                         │
│  User logs in with Instagram (via instaloader)          │
│       ↓                                                 │
│  App fetches following + followers lists LIVE           │
│       ↓                                                 │
│  Computes non-followers list (real-time, never stale)   │
│       ↓                                                 │
│  Fetches follower counts concurrently (3 threads)       │
│       ↓                                                 │
│  Shows profiles with full metadata                      │
│       ↓                                                 │
│  In-app unfollow with rate limit protection             │
│  (50/session cap, 15–30s randomized delay)              │
└─────────────────────────────────────────────────────────┘
```

### Why instaloader for premium (not official API)

Meta shut down the Instagram Basic Display API in December 2024. The replacement (Instagram Graph API) works only for business/creator accounts. For personal accounts, instaloader is the only viable live data source — it works by replicating a browser session, which is how every successful competitor app works under the hood. The risk is Instagram ToS violation (no automated mass actions); the mitigations are the rate limits already in the app (50 unfollows/session, 15–30s delay, human-initiated y/n per account).

### Free vs Premium: key differences at a glance

| Capability | Free (JSON export) | Premium (instaloader) |
|---|---|---|
| Data freshness | Stale (export takes up to 48h) | Real-time |
| Login required | No | Yes |
| Follower count sorting | No (export doesn't include it) | Yes (fetched live) |
| In-app unfollow | No (opens browser) | Yes |
| Rate limit protection | N/A | Built-in |
| Account ban risk | None | Low (human-paced) |

---

## Sequencing Recommendation

The website ships before the mobile app. It validates the product, generates revenue faster, and its architecture directly informs the mobile design — building mobile first would mean designing twice.

**Already done:** Refactor 4 (profile cache), Refactor 1 (concurrency), Refactor 2 (keyring).

| Step | Refactor | Why now |
|---|---|---|
| 1 | **Refactor 3** — Module split | Prerequisite for everything. Separates I/O from logic. |
| 2 | **Refactor 5** — Free-tier JSON export flow | Completes the free tier. Both flows ready. |
| 3 | **Refactor 6** — Website (FastAPI + Next.js) | Ship the web product. Start monetizing. |
| 4 | **Refactor 7** — Secure login (password-in, session-out) | Required for web login. Confidentiality pillar. |
| 5 | Mobile app (iOS + Android) | Built on validated web product. Reuses backend. |
| 6 | Future improvements | Whitelist, history, ghost detection, bulk mode, etc. |

---

## Refactor 1 — Concurrency for Follower-Count Lookups (Premium)

### Problem

`get_follower_counts()` (lines 182–199) fetches one profile at a time with a 3–7s sleep between each. For 200 non-followers: 10–24 minutes of wall time. This is the single biggest UX bottleneck in the premium flow.

The following/followers list fetch (`get_following_and_followers`) must stay sequential — instaloader's paginated generators share a single HTTP context and are not thread-safe.

### What to change

Replace the sequential loop with `concurrent.futures.ThreadPoolExecutor`:

- **3 workers maximum.** Each worker acquires a shared `threading.Lock` before calling `Profile.from_username`.
- **Per-request jitter:** Each worker sleeps before its request so threads don't fire simultaneously on startup.
- **Rate-limit sentinel `-2`:** Caller saves partial results and warns the user to resume later.

```python
import concurrent.futures
import threading

_api_lock = threading.Lock()

def _fetch_one(context, username: str) -> tuple[str, int]:
    jitter = random.uniform(FETCH_DELAY_MIN, FETCH_DELAY_MAX)
    time.sleep(jitter)
    with _api_lock:
        try:
            p = instaloader.Profile.from_username(context, username)
            return username, p.followers
        except instaloader.exceptions.TooManyRequestsException:
            return username, -2
        except Exception:
            return username, -1

def get_follower_counts(L, usernames: list[str], progress_callback=None) -> dict[str, int]:
    counts = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_fetch_one, L.context, u): u for u in usernames}
        for future in concurrent.futures.as_completed(futures):
            username, count = future.result()
            counts[username] = count
            if progress_callback:
                progress_callback(len(counts), len(usernames), username)
    return counts
```

### Speed improvement

| Approach | ~200 accounts |
|---|---|
| Current (sequential) | 10–24 min |
| 3 threads + lock | 3–8 min |
| 5+ threads (risky) | 2–5 min but rate-limit errors likely |

### Affected functions

- `get_follower_counts()` → rewrite in `core.py`
- New `_fetch_one()` + `_api_lock` in `core.py`
- `main()` in `cli.py` → handle `-2` sentinel, save partial count cache

---

## Refactor 2 — Credential Storage (Premium)

### Problem

`login()` calls `getpass.getpass()` every time the session file expires. For premium users who rely on the live flow daily, this is friction.

### Recommendation: OS keyring via `keyring` library

```python
import keyring

SERVICE_NAME = "instagram_unfollower"

def store_password(username: str, password: str) -> None:
    keyring.set_password(SERVICE_NAME, username, password)

def load_password(username: str) -> str | None:
    return keyring.get_password(SERVICE_NAME, username)
```

Updated login flow:

```
session file valid? → done (most common path)
else:
    password = load_password(username)
    if not password:
        password = getpass.getpass()
        ask: "Store password in OS keyring? [y/N]"
        if yes: store_password(username, password)
    L.login(username, password)
    save session file
```

**WSL2 caveat:** No GNOME Keyring daemon by default — `keyring` falls back to plaintext. Detect and warn:

```python
import keyring.backend as kb
if "plaintext" in type(kb.get_all_keyring()[0]).__name__.lower():
    print("  ⚠️  No secure keyring found. Password will NOT be stored.")
```

**Do not** store the password in `config.json` in any form. The session file already handles passwordless re-login while it is valid.

### Affected functions

- New `auth.py`: `login()`, `_do_two_factor_login()`, `_login_with_browser_cookies()`, `store_password()`, `load_password()`
- `requirements.txt`: add `keyring`

---

## Refactor 3 — UI-Ready Module Split (Both Flows)

### Problem

All logic lives in a single 415-line file. The new dual-flow design makes this worse — mixing free and premium paths in one file creates an unmaintainable tangle.

### Target module structure

```
unfviewer/
├── instagram_unfollower.py   # thin entry point (backward compat shim)
├── config.py                 # constants: MAX_UNFOLLOWS, delays, file names, plan gates
├── auth.py                   # instaloader login, 2FA, browser cookies, keyring
├── core_live.py              # premium flow: get_following_and_followers, get_follower_counts, unfollow_account
├── core_export.py            # free flow: parse_export_zip, parse_following_json, parse_followers_json
├── core.py                   # shared: compute_non_followers(followees, followers), sort_by_followers
├── storage.py                # config, progress, whitelist, CSV export, snapshot history
├── cli.py                    # interactive_unfollow, display_non_followers, main(), flow selector
├── api.py                    # (future) FastAPI REST layer — streams progress via SSE
└── tui.py                    # (future) Textual TUI
```

### core_live.py — premium, instaloader-powered

No `print`, no `input`, no top-level `time.sleep`. Progress via callbacks.

```python
def get_following_and_followers(
    profile: instaloader.Profile,
    progress_callback=None,
) -> tuple[dict[str, instaloader.Profile], set[str]]:
    """Returns (followees dict username→Profile, followers username set)."""
    ...

def get_follower_counts(
    L: instaloader.Instaloader,
    usernames: list[str],
    progress_callback=None,
) -> dict[str, int]:
    """Concurrent fetch, 3 workers, shared lock."""
    ...

def unfollow_account(
    L: instaloader.Instaloader,
    profile_obj: instaloader.Profile,
) -> bool:
    """Single unfollow. Raises TooManyRequestsException on rate-limit."""
    ...
```

### core_export.py — free tier, offline

Parses the ZIP or extracted folder from Instagram's data download.

```python
def parse_export(path: str) -> tuple[set[str], set[str]]:
    """
    Accepts either a .zip file path or an extracted folder path.
    Returns (following_usernames, follower_usernames).
    Handles both old (HTML) and new (JSON) export formats.
    """
    ...

def _parse_following_json(data: dict) -> set[str]:
    """Parses relationships_following.json structure."""
    ...

def _parse_followers_json(data: list) -> set[str]:
    """Parses followers_1.json structure."""
    ...
```

### core.py — shared between both flows

```python
def compute_non_followers(
    followees: dict[str, Any] | set[str],
    followers: set[str],
) -> set[str]:
    """Works with both Profile dicts (live) and username sets (export)."""
    return set(followees) - followers

def sort_by_followers(
    usernames: set[str],
    counts: dict[str, int],
) -> list[tuple[str, int]]:
    return sorted([(u, counts.get(u, 0)) for u in usernames], key=lambda x: x[1], reverse=True)
```

### cli.py — flow selector at startup

```python
def select_flow() -> str:
    """Returns 'premium' or 'free'."""
    print("  1. Live mode (Premium) — login with Instagram, real-time data")
    print("  2. Export mode (Free)  — import your Instagram data download")
    choice = input("  Choose [1/2]: ").strip()
    return "premium" if choice == "1" else "free"
```

### How the future API layer slots in

`api.py` (FastAPI) calls `core_live.*` or `core_export.*` depending on the user's plan, and streams progress to the frontend via Server-Sent Events. The `progress_callback` parameter in all core functions enables this without polling.

### instagram_unfollower.py — shim

```python
from cli import main
if __name__ == "__main__":
    main()
```

---

## Refactor 4 — Fix Fetch Flow + Eliminate Redundant Profile Re-fetch (Premium)

### Current flow: logically correct

```
get_followees()  →  following set
get_followers()  →  followers set
diff             →  non_followers
```

The set-difference is correct. Per-account check-back calls would cost O(n) individual API requests vs two paginated list fetches. Keep the batch-diff.

### Bug: redundant profile re-fetch before every unfollow (line 307)

```python
profile_obj = instaloader.Profile.from_username(L.context, username)  # unnecessary
L.unfollow(profile_obj)
```

`profile.get_followees()` already returns `Profile` objects. Cache them:

```python
# core_live.py
def get_following_and_followers(profile) -> tuple[dict[str, Profile], set[str]]:
    followees = {f.username: f for f in profile.get_followees()}
    followers = {f.username for f in profile.get_followers()}
    return followees, followers
```

Then `unfollow_account` receives the cached `Profile` object directly — zero extra API calls per unfollow.

### Affected functions

- `get_following_and_followers()` → moved to `core_live.py`, returns `dict[str, Profile]`
- `interactive_unfollow()` in `cli.py` → receives profile cache, no re-fetch
- `main()` → passes profile cache through

---

## Refactor 5 (New) — Free-Tier JSON Export Flow

### Instagram data export format

Instagram lets users request their data at **Settings → Account → Download your data → JSON format**. Delivery takes up to 48 hours. The relevant files inside the ZIP:

```
your_instagram_activity/
├── followers_and_following/
│   ├── following.json          # accounts you follow
│   └── followers_1.json        # your followers
```

**`following.json` structure:**
```json
{
  "relationships_following": [
    {
      "title": "",
      "media_list_data": [],
      "string_list_data": [{"value": "username", "timestamp": 1700000000}]
    }
  ]
}
```

**`followers_1.json` structure:**
```json
[
  {
    "title": "",
    "media_list_data": [],
    "string_list_data": [{"value": "username", "timestamp": 1700000000}]
  }
]
```

### Implementation in core_export.py

```python
import zipfile, json, os

def parse_export(path: str) -> tuple[set[str], set[str]]:
    if path.endswith(".zip"):
        return _parse_zip(path)
    return _parse_folder(path)

def _parse_zip(zip_path: str) -> tuple[set[str], set[str]]:
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        following_file = next(n for n in names if "following.json" in n)
        followers_file = next(n for n in names if "followers_1.json" in n)
        following = _parse_following_json(json.loads(zf.read(following_file)))
        followers = _parse_followers_json(json.loads(zf.read(followers_file)))
    return following, followers

def _parse_following_json(data: dict) -> set[str]:
    return {
        item["string_list_data"][0]["value"]
        for item in data.get("relationships_following", [])
        if item.get("string_list_data")
    }

def _parse_followers_json(data: list) -> set[str]:
    return {
        item["string_list_data"][0]["value"]
        for item in data
        if item.get("string_list_data")
    }
```

### Free-tier unfollow action

Since the free tier has no Instagram session, "unfollow" opens the profile in the browser:

```python
import webbrowser
webbrowser.open(f"https://www.instagram.com/{username}/")
```

The user unfollows manually inside Instagram. This is 100% ToS-safe.

### cli.py free-tier flow

```
User selects "Export mode"
  ↓
Prompt: "Path to your Instagram data ZIP or folder: "
  ↓
core_export.parse_export(path)
  ↓
core.compute_non_followers(following, followers)
  ↓
display list
  ↓
For each: y = open instagram.com/<username> | n = skip | q = quit
```

---

## Future Improvements

### 1. Whitelist
Protect specific accounts from ever being unfollowed. Stored in `whitelist.json`. Applies to both flows before display.

### 2. Dry-Run Mode
`--dry-run` flag: shows what would be unfollowed without making any mutation calls. Works in both flows.

### 3. CSV / Excel Export
Export non-follower list (username, follower count, profile URL, export date) to `.csv`.

### 4. Follower Change History
Snapshot non-follower lists by date. Diff snapshots to show who newly stopped following since last check. Lives in `storage.py`.

### 5. Rich Progress Bars
Replace `print()` during long fetches (premium flow) with `rich.progress.Progress`. Lowest-cost UX improvement before a full web UI.

### 6. Ghost Account Detection (Premium)
Filter non-followers who have 0 posts or haven't posted in N months before showing the list. Available only in premium because it requires live profile data.

### 7. Bulk Unfollow Mode (Premium)
`--bulk` flag: skips the `y/n` loop, unfollows all non-followers up to session cap with a single confirmation. Respects the same rate limits.

### 8. CLI Argument Parsing via `typer`
Replace `input()` prompts with `--username`, `--dry-run`, `--bulk`, `--limit N`, `--export-path` flags.

### 9. Scheduled / Auto Mode (Premium)
Cron / background mode: runs non-interactively, unfollows up to `max_unfollows_per_day` from saved progress, logs results to a daily file.

---

## Refactor 6 — Website Version

### Goal

Make the app accessible as a web application — no Python installation required on the user's side. The CLI code stays as the open-source core; the web app is the monetized product.

### UX principle: login → features, nothing else

The entire UI must reduce to two states:

```
┌─────────────────────┐        ┌──────────────────────────────┐
│                     │        │                              │
│   Login screen      │  ───▶  │   Dashboard (all features)   │
│   username          │        │   - Non-followers list        │
│   password          │        │   - Unfollow flow            │
│   [Login button]    │        │   - Stats                    │
│                     │        │                              │
└─────────────────────┘        └──────────────────────────────┘
```

There is no onboarding flow, no plan selection before login, no "how it works" interstitial. The user logs in and the app works. Plan gating (free vs premium) is surfaced inline — e.g., a lock icon on premium features — never as a barrier before login.

### Architecture

```
Browser (React / Next.js)
        │  HTTPS + SSE (progress streaming)
        ▼
FastAPI backend (Python)
        │
        ├── Free flow:  user uploads Instagram data ZIP → parsed in memory → result returned
        └── Premium flow: instaloader session per user → live fetch → in-app unfollow
```

**Key principles:**
- Free tier analysis runs entirely in the request cycle — no state stored on the server
- Premium sessions are stored server-side, encrypted per user (AES-256), never logged
- Progress is streamed via **Server-Sent Events** (SSE) using the `progress_callback` hooks already in `core_live.py`
- All unfollow actions are user-initiated from the frontend — the backend performs the API call only after receiving an explicit per-account command

### Recommended stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | Next.js (React) | SSR, easy deployment on Vercel |
| Backend | FastAPI (Python) | Native async, SSE support, reuses existing core modules |
| Session store | Redis | Encrypted session tokens, TTL expiry |
| Auth | Session cookie (HTTP-only, SameSite=Strict) | No JWT complexity for MVP |
| Deployment | Fly.io or Railway | Cheap, Docker-native, supports persistent volumes |

### FastAPI endpoint sketch

```python
# api.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from core_live import get_following_and_followers, get_follower_counts
from auth import login_from_session_token

app = FastAPI()

@app.get("/non-followers")
async def non_followers(session_token: str):
    L, profile = login_from_session_token(session_token)
    # Stream progress back to the browser via SSE
    async def event_stream():
        followees, followers = await asyncio.to_thread(
            get_following_and_followers, profile,
            progress_callback=lambda done, total, u: ...
        )
        ...
    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/unfollow/{username}")
async def unfollow(username: str, session_token: str):
    L, _ = login_from_session_token(session_token)
    profile = get_cached_profile(username)
    unfollow_user(L, profile)
    return {"status": "ok"}
```

### Rate limit handling on the web

The web version must enforce the same safety limits as the CLI:
- 50 unfollows per user per session (tracked server-side per session token)
- 15–30s enforced delay between unfollow calls server-side (the frontend cannot override this)
- `TooManyRequestsException` → 429 response → frontend shows cooldown UI

### Module split prerequisite

The website version requires **Refactor 3** (module split) to be complete first. The FastAPI routes call `core_live.*` and `core_export.*` directly — there must be no CLI I/O (`print`, `input`, `time.sleep`) in those modules.

---

## Refactor 7 — Secure Login: Password In, Session Out

### User-facing flow (CLI and Web)

The user only ever does one thing: **type their Instagram username and password**. The app handles everything else. No DevTools, no cookie copying, no technical steps.

```
User types username + password
        ↓
App authenticates via instaloader (L.login)
        ↓
Password is immediately discarded from memory
        ↓
Instaloader session token saved (encrypted)
        ↓
All future runs use the session token — no password needed again
        ↓
If session expires → user types password once more → repeat
```

### Security model

| What | Stored? | Where | How long |
|---|---|---|---|
| Password | Never | — | — |
| Instagram session token | Yes | `.session_<user>` (CLI) / Redis (web) | Until expired or logged out |
| Follower/following data | No | — | — |
| Username | Yes | `config.json` (CLI) / Redis (web) | Until user clears it |

The password passes through process memory only during the login call and is never written to disk, logged, or transmitted anywhere except to Instagram's own servers over HTTPS.

### CLI — already implemented

The current `login()` function already follows this model:
- `getpass.getpass()` reads the password without echoing
- `L.login(username, senha)` sends it directly to Instagram
- `L.save_session_to_file(session_file)` persists only the session token
- The `senha` variable goes out of scope immediately after

The only improvement needed: make the "session restored" path the obvious happy path and surface a clearer message when re-login is required.

### Web app login flow

```
User visits app.com/login
        ↓
Form: Instagram username + password (HTTPS only, never logged)
        ↓
POST /auth/login → backend calls L.login(username, password)
        ↓
Password variable discarded immediately after instaloader call
        ↓
Session token encrypted (AES-256) and stored in Redis with 24h TTL
        ↓
User receives an HTTP-only SameSite=Strict app session cookie
        ↓
All subsequent requests use the app cookie to retrieve the encrypted
Instagram session token from Redis — password is never involved again
```

### What lives in Redis (web)

```json
{
  "ig_session_enc": "<AES-256 encrypted instaloader session bytes>",
  "username": "gb_luzz",
  "unfollow_count_today": 12,
  "expires_at": 1714300000
}
```

- `ig_session_enc` — the encrypted instaloader session (equivalent to `.session_<user>` on disk)
- Encryption key lives in an environment variable, never in the database
- On logout or TTL expiry, the Redis key is deleted — the session is gone and unrecoverable

### 2FA handling (web)

When `TwoFactorAuthRequiredException` is raised during login, the backend returns `{"status": "2fa_required"}`. The frontend shows a 6-digit code input. The user submits the code; the backend calls `L.two_factor_login(code)` and then saves the session.

### What is never stored

- Instagram password (anywhere, ever)
- Follower/following lists (request-scoped only)
- Unfollow history beyond the session counter
- Any personal data beyond username + encrypted session token

---

## Summary Table

| Item | Effort | Impact | Tier | Unblocks |
|---|---|---|---|---|
| Refactor 4 — Fix fetch flow / profile cache | Low | Medium | Premium | 1, 3 |
| Refactor 3 — Module split (both flows) | Medium | High | Both | All |
| Refactor 5 — JSON export flow | Medium | High | Free | Free tier launch |
| Refactor 1 — Concurrency in follower-count fetch | Medium | High (speed) | Premium | — |
| Refactor 2 — Keyring credential storage | Low | Medium (UX) | Premium | — |
| **Refactor 6 — Website version (FastAPI + Next.js)** | High | Very High | Both | Module split |
| **Refactor 7 — Session cookie login (no password)** | Low | High (security) | Both | — |
| Whitelist | Low | High (safety) | Both | — |
| Dry-run mode | Low | High (safety) | Both | — |
| CSV export | Low | Medium | Both | Storage module |
| History / change tracking | Medium | Medium | Both | Storage module |
| Rich progress bars | Low | High (UX) | Premium | Web UI |
| Ghost account detection | Medium | Medium | Premium | core_live.py |
| Bulk unfollow mode | Low | Medium | Premium | — |
| `typer` CLI args | Low | Medium | Both | API layer |
| Scheduled / auto mode | Medium | Medium | Premium | Module split |
