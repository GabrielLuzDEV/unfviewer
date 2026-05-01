"""
Development data cache — run this ONCE to snapshot your real Instagram data.
After that, the backend serves from the snapshot instead of hitting Instagram.

Usage:
    python dev_data.py snapshot          # fetch from Instagram → saves dev_snapshot.json
    python dev_data.py show              # print what's in the snapshot

The snapshot is gitignored. Delete it to force a fresh fetch.
"""

import json
import os
import sys

SNAPSHOT_FILE = "dev_snapshot.json"


def snapshot():
    from auth import login
    from storage import load_config
    from core_live import get_following_and_followers
    from core import compute_non_followers

    config = load_config()
    username = config.get("username", "").strip()
    if not username:
        print("No username in config.json. Run the CLI once first.")
        sys.exit(1)

    print(f"Fetching data for @{username} (one-time snapshot)...")
    L, profile = login(username)
    followees, followers = get_following_and_followers(profile)
    dont_follow_back = compute_non_followers(followees, followers)

    data = {
        "username": username,
        "followees": list(followees.keys()),
        "followers": list(followers),
        "non_followers": list(dont_follow_back),
    }
    with open(SNAPSHOT_FILE, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\n✅ Snapshot saved to {SNAPSHOT_FILE}")
    print(f"   {len(followees)} following, {len(followers)} followers, {len(dont_follow_back)} non-followers")
    print(f"\nSet DEV_SNAPSHOT=1 in .env to use this data instead of live Instagram calls.")


def show():
    if not os.path.exists(SNAPSHOT_FILE):
        print(f"No snapshot found. Run: python dev_data.py snapshot")
        sys.exit(1)
    with open(SNAPSHOT_FILE) as f:
        data = json.load(f)
    print(f"Username:      @{data['username']}")
    print(f"Following:     {len(data['followees'])}")
    print(f"Followers:     {len(data['followers'])}")
    print(f"Non-followers: {len(data['non_followers'])}")
    print(f"\nFirst 10 non-followers:")
    for u in data["non_followers"][:10]:
        print(f"  @{u}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    if cmd == "snapshot":
        snapshot()
    elif cmd == "show":
        show()
    else:
        print(__doc__)
