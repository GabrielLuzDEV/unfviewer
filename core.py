"""Pure computation: non-follower diffing and sorting. No I/O, no instaloader imports."""

from typing import Any


def compute_non_followers(
    followees: dict[str, Any],   # username → Profile (or any truthy value)
    followers: set[str],
) -> set[str]:
    return set(followees.keys()) - followers


def sort_by_followers(
    non_followers: set[str],
    counts: dict[str, int],
) -> list[tuple[str, int]]:
    return sorted(
        [(u, counts.get(u, 0)) for u in non_followers],
        key=lambda x: x[1],
        reverse=True,
    )
