# Runtime constants shared by CLI, web backend, and future mobile backend.
# Change values here; never hardcode them inline.

# ── Unfollow rate limiting ────────────────────────────────────────────────────
MAX_UNFOLLOWS_PER_SESSION = 50
FREE_UNFOLLOW_LIMIT = 10            # unfollows before freemium gate on free tier

UNFOLLOW_DELAY_MIN = 4              # seconds (server-enforced before each unfollow)
UNFOLLOW_DELAY_MAX = 8

UNFOLLOW_COOLDOWN_EVERY = 5         # unfollow actions before mandatory long pause
UNFOLLOW_COOLDOWN_SEC = 300         # 5-minute pause (matches davidarroyo1234 OSS research)

# ── Fetch rate limiting (instagrapi delay_range) ──────────────────────────────
# These are passed to instagrapi's Client.delay_range — applied between every
# private API request automatically.
FETCH_PAGE_DELAY_MIN = 0.5          # seconds between paginated fetch requests
FETCH_PAGE_DELAY_MAX = 2.0

FETCH_LONG_PAUSE_EVERY = 6          # pages before a longer pause
FETCH_LONG_PAUSE_SEC = 10           # seconds for the longer pause

# ── Caching ───────────────────────────────────────────────────────────────────
PROFILE_CACHE_TTL = 86_400          # 24 h in seconds

# ── Legacy CLI constants (kept for backward compat) ──────────────────────────
FETCH_DELAY_MIN = 3                 # seconds between concurrent follower-count requests
FETCH_DELAY_MAX = 7

PROGRESS_FILE = "unfollow_progress.json"
CONFIG_FILE = "config.json"
PROFILE_CACHE_FILE = "profile_cache.json"

_KEYRING_SERVICE = "instagram_unfollower"
