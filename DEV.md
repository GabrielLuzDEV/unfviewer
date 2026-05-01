# Developer Guide — Running Locally

This file explains how to run and test each layer: CLI, backend API, and frontend.

---

## Project structure

```
unfviewer/
├── config.py           constants (delays, caps, file paths)
├── storage.py          disk I/O (config, progress, profile cache)
├── auth.py             login, keyring, 2FA
├── core.py             pure logic (diff, sort)
├── core_live.py        instaloader: fetch lists, follower counts, unfollow
├── core_export.py      free tier: parse Instagram data export ZIP
├── cli.py              interactive CLI loop + main()
├── instagram_unfollower.py   entry point shim → cli.main()
│
├── backend/
│   ├── main.py         FastAPI app
│   ├── models.py       Pydantic request/response shapes
│   ├── session_store.py in-memory session registry
│   ├── routes/
│   │   ├── auth.py     POST /auth/login, /auth/2fa, /auth/logout
│   │   ├── followers.py GET /followers/non-followers/stream (SSE)
│   │   └── unfollow.py POST /unfollow/{username}
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx        login page
│   │   └── dashboard/
│   │       └── page.tsx    non-follower list + unfollow flow
│   └── components/
│       ├── LoginForm.tsx
│       ├── NonFollowerList.tsx
│       └── UnfollowCard.tsx
│
└── docker-compose.yml  local dev: backend only (no Redis needed yet)
```

---

## 1. CLI

The fastest way to test any Python logic change.

```bash
# One-time setup
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install instaloader keyring

# Run
python instagram_unfollower.py
```

**What each module does at runtime:**

| Module | How to test in isolation |
|--------|--------------------------|
| `storage.py` | `python -c "from storage import load_config; print(load_config())"` |
| `core.py` | `python -c "from core import compute_non_followers; print(compute_non_followers({'a':None,'b':None},{'b'}))"` |
| `core_export.py` | `python -c "from core_export import parse_export; f,fl=parse_export('path/to/export.zip'); print(len(f),len(fl))"` |
| `auth.py` | Runs as part of `instagram_unfollower.py` — no isolated test needed |
| `core_live.py` | Runs as part of `instagram_unfollower.py` |

**Test the JSON export flow (free tier, no Instagram login needed):**

```bash
python -c "
from core_export import parse_export
from core import compute_non_followers, sort_by_followers

followees, followers = parse_export('path/to/your/instagram-export.zip')
non = compute_non_followers(followees, followers)
print(f'{len(non)} accounts don\'t follow back')
"
```

---

## 2. Backend (FastAPI)

### Option A — direct (fastest for development)

```bash
cd /home/user/personal/unfviewer
source .venv/bin/activate
pip install fastapi "uvicorn[standard]" pydantic python-multipart

uvicorn backend.main:app --reload --port 8000
```

The `--reload` flag auto-restarts when you edit any `.py` file.

**Swagger UI** (interactive API docs):
```
http://localhost:8000/docs
```

**Test endpoints with curl:**

```bash
# Health check
curl http://localhost:8000/health

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"yourusername","password":"yourpassword"}'

# Fetch non-followers (SSE stream — paste session_id from login response)
curl -N "http://localhost:8000/followers/non-followers/stream?session_id=<SID>"

# Unfollow
curl -X POST http://localhost:8000/unfollow/targetusername \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<SID>","username":"targetusername"}'
```

### Option B — Docker (matches production)

```bash
docker-compose up --build
```

Backend available at `http://localhost:8000`.

---

## 3. Frontend (Next.js)

Requires Node.js 18+.

```bash
cd frontend
npm install
npm run dev
```

Frontend available at `http://localhost:3000`.

The frontend reads `NEXT_PUBLIC_API_URL` to find the backend.
Default is `http://localhost:8000` (set in `next.config.ts`).

**Full local stack in two terminals:**

```bash
# Terminal 1 — backend
cd /home/user/personal/unfviewer
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend
cd /home/user/personal/unfviewer/frontend
npm run dev
```

Then open `http://localhost:3000`.

---

## 4. Environment variables

| Variable | Where | Description |
|----------|-------|-------------|
| `NEXT_PUBLIC_API_URL` | frontend `.env.local` | Backend URL. Default: `http://localhost:8000` |

Create `frontend/.env.local` to override:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 5. What changes where

| I want to change... | Edit this file |
|--------------------|----------------|
| Rate limits / delays | `config.py` |
| Free unfollow cap | `config.py` → `FREE_UNFOLLOW_LIMIT` |
| Login flow | `auth.py` (CLI) or `backend/routes/auth.py` (web) |
| Unfollow logic | `core_live.py` → `unfollow_user()` |
| Non-follower diff | `core.py` |
| JSON export parsing | `core_export.py` |
| Login page UI | `frontend/app/page.tsx` + `frontend/components/LoginForm.tsx` |
| Dashboard UI | `frontend/app/dashboard/page.tsx` |
| Account card UI | `frontend/components/UnfollowCard.tsx` |
| API routes | `backend/routes/*.py` |
| Session management | `backend/session_store.py` |

---

## 6. Verify the module split didn't break the CLI

```bash
source .venv/bin/activate
python -c "from cli import main; print('imports OK')"
python instagram_unfollower.py
```
