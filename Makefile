SHELL    := /bin/bash
PYTHON   := .venv/bin/python
PIP      := .venv/bin/pip
UVICORN  := .venv/bin/uvicorn

.PHONY: help setup setup-py setup-frontend env cli session \
        backend backend-docker backend-docker-stop frontend dev check \
        deploy-frontend deploy-backend proxy-test

# ── Default ───────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "Development:"
	@echo "  make setup              Install all dependencies (Python venv + npm)"
	@echo "  make env                Create .env and frontend/.env.local from examples"
	@echo "  make dev                Run backend :8000 + frontend :3000 (Ctrl+C stops both)"
	@echo "  make backend            FastAPI with auto-reload"
	@echo "  make frontend           Next.js dev server"
	@echo "  make backend-docker     Run backend via Docker Compose"
	@echo "  make check              Verify Python module imports"
	@echo ""
	@echo "Instagram session:"
	@echo "  make session IGUSER=<username>   Bootstrap/refresh session file (when login is blocked)"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy-frontend    Deploy Next.js to Vercel"
	@echo "  make deploy-backend     Push backend Docker image to Render"
	@echo "  make proxy-test         Check that INSTAGRAM_PROXY is reachable"
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────
setup: setup-py setup-frontend
	@echo ""
	@echo "✅  Setup complete. Run 'make env' next if this is your first time."

setup-py:
	@echo "→ Creating Python virtual environment..."
	python3 -m venv .venv
	$(PIP) install --upgrade pip --quiet
	$(PIP) install -r backend/requirements.txt --quiet
	@echo "✅  Python dependencies installed."

setup-frontend:
	@echo "→ Installing frontend dependencies..."
	cd frontend && npm install --silent
	@echo "✅  Frontend dependencies installed."

# ── Environment files ─────────────────────────────────────────────────────────
env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✅  Created .env — edit SECRET_KEY and INSTAGRAM_PROXY before deploying."; \
	else \
		echo "ℹ️   .env already exists, skipping."; \
	fi
	@if [ ! -f frontend/.env.local ]; then \
		cp frontend/.env.example frontend/.env.local; \
		echo "✅  Created frontend/.env.local from example."; \
	else \
		echo "ℹ️   frontend/.env.local already exists, skipping."; \
	fi

# ── CLI ───────────────────────────────────────────────────────────────────────
cli:
	$(PYTHON) instagram_unfollower.py

# ── Session bootstrap (when Instagram blocks automated login from this IP) ────
session:
	@if [ -z "$(IGUSER)" ]; then \
		echo "Usage: make session IGUSER=your_instagram_username"; exit 1; \
	fi
	$(PYTHON) -m instaloader --login $(IGUSER)

# ── Backend ───────────────────────────────────────────────────────────────────
backend:
	@lsof -ti:8000 | xargs -r kill 2>/dev/null || true
	$(UVICORN) backend.main:app --reload --port 8000

backend-docker:
	docker-compose up --build

backend-docker-stop:
	docker-compose down

# ── Frontend ──────────────────────────────────────────────────────────────────
frontend:
	@lsof -ti:3000 | xargs -r kill 2>/dev/null || true
	cd frontend && npm run dev

# ── Dev (both at once) ────────────────────────────────────────────────────────
dev:
	@lsof -ti:8000 | xargs -r kill 2>/dev/null || true
	@lsof -ti:3000 | xargs -r kill 2>/dev/null || true
	@echo "→ Starting backend on :8000 and frontend on :3000"
	@echo "   Press Ctrl+C to stop both."
	@trap 'kill 0' SIGINT; \
		$(UVICORN) backend.main:app --reload --port 8000 & \
		cd frontend && npm run dev

# ── Deployment ────────────────────────────────────────────────────────────────
deploy-frontend:
	@command -v vercel >/dev/null 2>&1 || { echo "Install Vercel CLI: npm install -g vercel"; exit 1; }
	cd frontend && vercel --prod

deploy-backend:
	@echo "Push your code to GitHub — Render deploys automatically from the main branch."
	@echo "Or trigger a manual deploy at: https://dashboard.render.com"

proxy-test:
	@if [ -z "$$INSTAGRAM_PROXY" ]; then \
		echo "⚠️   INSTAGRAM_PROXY is not set. Set it in .env or export it."; exit 1; \
	fi
	@echo "Testing proxy: $$INSTAGRAM_PROXY"
	$(PYTHON) -c "\
import os, urllib.request; \
proxy = os.environ['INSTAGRAM_PROXY']; \
h = urllib.request.ProxyHandler({'https': proxy, 'http': proxy}); \
opener = urllib.request.build_opener(h); \
r = opener.open('https://httpbin.org/ip', timeout=10); \
print('Proxy OK. External IP:', __import__('json').loads(r.read())['origin'])"

# ── Health check ─────────────────────────────────────────────────────────────
check:
	@$(PYTHON) -c "\
from config import MAX_UNFOLLOWS_PER_SESSION, UNFOLLOW_COOLDOWN_EVERY; \
from core import compute_non_followers; \
from core_live import unfollow_user, _make_client; \
from core_export import parse_export; \
print('✅  All module imports OK')"
