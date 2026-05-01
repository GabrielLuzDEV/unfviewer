# unfviewer — Development Guide

## What this app does

unfviewer finds Instagram users that you follow but who don't follow you back, and lets you unfollow them one at a time with rate-limit protection. It has two modes:

- **Live mode** (requires Instagram login): uses instagrapi (Instagram's private mobile API) for real-time data and in-app unfollowing
- **Export mode** (no login required): parses the ZIP from Instagram's GDPR data export locally, zero Instagram API calls

## Architecture

```
frontend/          Next.js 14 (App Router) — deployed on Vercel
backend/           FastAPI (Python 3.12) — deployed on Render
  main.py          App factory, CORS, security headers, rate limiting, eviction loop
  routes/
    auth.py        Login (password / 2FA / sessionid cookie), logout
    followers.py   SSE stream for non-follower fetch
    unfollow.py    Per-user unfollow with server-enforced delays
    export.py      GDPR ZIP analysis — no auth, no Instagram calls
  session_store.py In-memory sessions, Fernet-encrypted on-disk persistence
  dependencies.py  get_current_session FastAPI dependency (reads httpOnly cookie)
  middleware/
    rate_limit.py  slowapi limiter (5 req/min on auth endpoints)
core_live.py       instagrapi calls: fetch_followees, fetch_followers, unfollow_user
core_export.py     ZIP parser: parse_export(path) → (followees_dict, followers_set)
core.py            compute_non_followers(followees, followers) → set[str]
config.py          All tunable constants — change here, never inline
```

## Instagram API patterns (from OSS research — validated 2026)

### How the private mobile API works

instagrapi impersonates Instagram's Android app. The key endpoints:

```
GET  /api/v1/friendships/{user_id}/following/?max_id={cursor}
GET  /api/v1/friendships/{user_id}/followers/?max_id={cursor}
POST /api/v1/friendships/destroy/{user_id}/   ← unfollow
```

These are the same endpoints used by the official Instagram Android app. The server identifies the client by the session cookie (`sessionid`), not by IP.

### Authentication approaches (ranked best→worst for server-side use)

1. **`sessionid` cookie** — user copies from browser DevTools. Bypasses the `/api/v1/accounts/login/` endpoint entirely. Most reliable, no IP required for auth step. Used in `login-cookie` route.
2. **Password login via instagrapi** — hits `/api/v1/accounts/login/`. Works from clean IPs but triggers challenges from datacenter IPs. Used in `login` route.
3. **GDPR export** — zero Instagram API calls. Never gets banned. Used in `export` route. Only limitation: data is up to 48h stale.

### Rate limiting rules (proven by davidarroyo1234, the most battle-tested OSS project)

**Fetch (reading followers/following):**
- 500–2000ms random delay between paginated pages
- 10-second pause every 6 pages
- With `instagrapi`'s `delay_range = [0.5, 2.0]` this is automatic

**Unfollow (write operation — much stricter limits):**
- 4–8s random delay before each unfollow (set in config.py)
- 5-minute mandatory pause after every 5 consecutive unfollows
- Never exceed ~60 unfollows per hour total
- Server enforces both — the frontend cannot skip them

**Why these numbers:**
Instagram's anti-automation detection looks at:
1. Request frequency (solved by delays)
2. Action velocity (solved by the 5-unfollow cooldown)
3. Deviation from human patterns (solved by randomization)
4. IP reputation (solved by proxy support)

## The IP Blacklist Problem

Instagram pre-blocks most cloud provider IP ranges (AWS, GCP, Azure, Railway, Render, Fly.io, DigitalOcean, etc.). Server-side Instagram calls from these IPs either fail immediately or trigger challenges.

### Defense strategy (three layers)

**Layer 1: Export mode** — no network calls to Instagram at all. Always works. Recommend for casual users.

**Layer 2: Residential proxy** — set `INSTAGRAM_PROXY` in the backend's `.env`:
```
INSTAGRAM_PROXY=socks5://user:pass@proxy.provider.com:10000
```
Supported formats: `socks5://`, `http://`, `https://`. The proxy must be a residential IP (not another datacenter).

Free/cheap residential proxy options:
- WebShare.io — free tier: 10 proxies, 1GB/mo
- BrightData — pay-per-use, ~$3/GB
- IPRoyal — from $1.75/GB
- Your home router as a SOCKS5 proxy (SSH tunnel or dedicated proxy app)

**Layer 3: Run the backend locally** — during development, your machine's residential IP is used. Zero ban risk. Use `make dev`.

For Cloudflare Tunnel (expose local backend publicly without port forwarding):
```bash
cloudflared tunnel --url http://localhost:8000
```
Then set `NEXT_PUBLIC_API_URL` to the cloudflared URL.

### instagrapi proxy configuration

```python
from instagrapi import Client

cl = Client()
cl.delay_range = [0.5, 2.0]   # random delay between each private API request

if proxy := os.environ.get("INSTAGRAM_PROXY"):
    cl.set_proxy(proxy)
```

This is done in `core_live._make_client()` — all three login paths use this helper.

## Development workflow

```bash
# First time setup
make setup         # creates .venv, installs deps, npm install
make env           # creates .env and frontend/.env.local from examples

# Daily development
make dev           # starts backend :8000 + frontend :3000 concurrently

# Individual services
make backend       # FastAPI with auto-reload
make frontend      # Next.js dev server

# Session bootstrap (when Instagram blocks automated login from your IP)
make session IGUSER=your_username   # uses instaloader CLI to create session file

# Verify imports are healthy
make check
```

### Session files

Session files live in `backend/.sessions/{username}.enc` (Fernet-encrypted). They're loaded automatically on login — if a valid session file exists, the password is never sent to Instagram again.

If the session expires or Instagram invalidates it, the file is deleted and a fresh login is required.

## Production deployment

### Frontend — Vercel (free)

```bash
# One-time setup
npm install -g vercel
cd frontend && vercel login

# Deploy
make deploy-frontend
# or: cd frontend && vercel --prod
```

Required environment variable in Vercel dashboard:
- `NEXT_PUBLIC_API_URL` = `https://your-backend.onrender.com`

### Backend — Render (free tier, 512MB RAM, spins down after 15min inactivity)

1. Push code to GitHub
2. Create a new Web Service on Render, connect repo
3. Set Dockerfile path: `backend/Dockerfile`
4. Set environment variables (see `.env.example`)
5. `make deploy-backend` to trigger redeploy

**Critical env vars for production:**
```
SECRET_KEY=<generated with: python -c "import secrets; print(secrets.token_hex(32))">
ENVIRONMENT=production
COOKIE_SECURE=true
ALLOWED_ORIGINS=https://your-app.vercel.app
INSTAGRAM_PROXY=socks5://...    (required for non-blocked IP)
```

### Alternative backend hosts (if Render doesn't work for your use case)

| Host | Free tier | Notes |
|------|-----------|-------|
| Railway | 500 hours/mo free | Good DX, IPs vary |
| Fly.io | 3 shared VMs free | Most flexible, needs `fly.toml` |
| Koyeb | 1 instance free | European IPs |
| Oracle Cloud | Always free | ARM VMs, needs manual setup |
| **Self-hosted VPS** | Hetzner €3/mo | Full control, best for proxy setup |

## Security model

See `backend/routes/auth.py` and `backend/session_store.py` for implementation.

Key properties:
- Instagram password → never stored, discarded immediately after instagrapi call
- Session tokens → encrypted at rest with Fernet (AES-128-CBC), key derived via PBKDF2-SHA256 from `SECRET_KEY`
- Session IDs → live in an `httpOnly; SameSite=Lax` cookie, never in URLs or localStorage
- Rate limiting → 5 auth attempts/minute per IP (via slowapi)
- Input validation → Pydantic validators on all models (username regex, password length, etc.)
- Error messages → generic to client, full details to server logs only

## Adding new features

### New backend route
1. Create `backend/routes/myfeature.py` with an `APIRouter`
2. Import and include in `backend/main.py`
3. Protected routes: add `s: Session = Depends(get_current_session)` parameter
4. Public routes: no dependency needed

### Changing rate limits
Edit `config.py` — all tunable constants are there. Never hardcode delays inline.

### Changing timing for Instagram API calls
`core_live._make_client()` sets `cl.delay_range`. Adjust there.
