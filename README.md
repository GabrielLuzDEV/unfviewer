# Instagram Non-Follower Finder

Find who doesn't follow you back on Instagram and selectively unfollow them — one account at a time.

## Requirements

- Python 3.10+
- [instaloader](https://instaloader.github.io/)

## Installation

```bash
python -m venv .venv
```

Activate the virtual environment:

- **Linux/macOS:** `source .venv/bin/activate`
- **Windows:** `.venv\Scripts\activate`

Then install the dependency:

```bash
pip install instaloader
```

## Usage

```bash
python instagram_unfollower.py
```

On first run, you'll be asked for your Instagram username. It's saved to `config.json` so you won't need to type it again.

## Login

The script will prompt for your password (never stored). After a successful login, the session is saved to `.session_<username>` so future runs log in automatically.

### Two-Factor Authentication (2FA)

If your account has 2FA enabled, you'll be prompted for the 6-digit code. If the code is rejected, you can fall back to browser cookies:

1. Open [instagram.com](https://www.instagram.com) in your browser (already logged in)
2. Press `F12` → **Application** → **Cookies** → `https://www.instagram.com`
3. Copy the values of `sessionid` and `csrftoken` and paste them when prompted

## Interactive Unfollow

After fetching your following/followers lists, each non-follower is shown one by one:

| Key | Action |
|-----|--------|
| `y` | Unfollow this account (with a safe delay) |
| `n` | Keep following (skip to next) |
| `p` | Pause and save progress to resume later |
| `q` | Quit immediately without saving |

## Safety Limits

| Setting | Value |
|---------|-------|
| Max unfollows per session | 50 |
| Delay between unfollows | 40–70 seconds (randomized) |
| Recommended daily limit | ~100–150 unfollows total |

The script stops automatically if Instagram returns a rate-limit error and saves your progress.

## Resuming a Paused Session

If you press `p` or hit the session cap, progress is saved to `unfollow_progress.json`. On the next run you'll be asked if you want to resume where you left off.

## Generated Files

| File | Description |
|------|-------------|
| `config.json` | Saves your Instagram username |
| `.session_<username>` | Saved login session (auto-login on future runs) |
| `unfollow_progress.json` | Progress checkpoint (created on pause/cap) |
