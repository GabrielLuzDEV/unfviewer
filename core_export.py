"""
Free-tier data source: parse an Instagram data export ZIP or folder.

Instagram export path: Settings → Your activity → Download your information
Select JSON format. The relevant files are:
  connections/followers_and_following/following.json
  connections/followers_and_following/followers_1.json  (may be paginated)

Returns the same shapes as core_live so callers are interchangeable:
  followees: dict[str, None]   (no Profile object — export has no follower counts)
  followers: set[str]
"""

import json
import os
import zipfile
from pathlib import Path


def _read_usernames(data: list[dict]) -> set[str]:
    """Extract usernames from Instagram export list structure."""
    result: set[str] = set()
    for item in data:
        # Each item is {"title": "", "media_list_data": [], "string_list_data": [{"value": username, ...}]}
        for entry in item.get("string_list_data", []):
            val = entry.get("value", "").strip()
            if val:
                result.add(val)
    return result


def _load_json_from_zip(zf: zipfile.ZipFile, name: str) -> list:
    names = zf.namelist()
    match = next((n for n in names if n.endswith(name)), None)
    if not match:
        return []
    with zf.open(match) as f:
        return json.load(f)


def _load_json_from_dir(root: Path, name: str) -> list:
    candidate = root / name
    if not candidate.exists():
        # Try paginated e.g. followers_1.json
        base = name.replace(".json", "")
        for i in range(1, 20):
            p = root / f"{base}_{i}.json"
            if p.exists():
                with open(p) as f:
                    return json.load(f)
    if candidate.exists():
        with open(candidate) as f:
            return json.load(f)
    return []


def parse_export(path: str) -> tuple[dict[str, None], set[str]]:
    """
    Parse an Instagram data export ZIP file or extracted folder.
    Returns (followees dict, followers set) — same interface as core_live.
    """
    p = Path(path)

    if p.suffix == ".zip" and p.is_file():
        with zipfile.ZipFile(p) as zf:
            following_raw = _load_json_from_zip(zf, "following.json")
            followers_raw = _load_json_from_zip(zf, "followers_1.json")
    elif p.is_dir():
        follow_dir = p / "connections" / "followers_and_following"
        following_raw = _load_json_from_dir(follow_dir, "following.json")
        followers_raw = _load_json_from_dir(follow_dir, "followers_1.json")
    else:
        raise ValueError(f"Path must be a .zip file or extracted folder: {path}")

    # following.json wraps the list under a "relationships_following" key
    if isinstance(following_raw, dict):
        following_raw = following_raw.get("relationships_following", [])

    followees_usernames = _read_usernames(following_raw)
    followers_usernames = _read_usernames(followers_raw)

    followees: dict[str, None] = {u: None for u in followees_usernames}
    return followees, followers_usernames
