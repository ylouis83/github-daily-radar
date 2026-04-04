"""Fetch AI builders feed from the follow-builders GitHub repo.

This is the Python equivalent of follow-builders' prepare-digest.js.
All content is fetched centrally — no API keys required.
"""
from __future__ import annotations

import httpx

FEED_X_URL = "https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-x.json"
FEED_PODCASTS_URL = "https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-podcasts.json"
FEED_BLOGS_URL = "https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-blogs.json"

TIMEOUT = 30.0


def fetch_feeds() -> dict:
    """Fetch all three feeds and return a merged dict.

    Returns a dict with keys: x, podcasts, blogs, stats, errors.
    Never raises — returns partial data on failure.
    """
    errors: list[str] = []
    feed_x: dict | None = None
    feed_podcasts: dict | None = None
    feed_blogs: dict | None = None

    with httpx.Client(timeout=TIMEOUT) as client:
        try:
            resp = client.get(FEED_X_URL)
            resp.raise_for_status()
            feed_x = resp.json()
        except Exception as exc:
            errors.append(f"Could not fetch tweet feed: {exc}")

        try:
            resp = client.get(FEED_PODCASTS_URL)
            resp.raise_for_status()
            feed_podcasts = resp.json()
        except Exception as exc:
            errors.append(f"Could not fetch podcast feed: {exc}")

        try:
            resp = client.get(FEED_BLOGS_URL)
            resp.raise_for_status()
            feed_blogs = resp.json()
        except Exception as exc:
            errors.append(f"Could not fetch blog feed: {exc}")

    x_items = (feed_x or {}).get("x", [])
    podcast_items = (feed_podcasts or {}).get("podcasts", [])
    blog_items = (feed_blogs or {}).get("blogs", [])

    return {
        "x": x_items,
        "podcasts": podcast_items,
        "blogs": blog_items,
        "stats": {
            "xBuilders": len(x_items),
            "totalTweets": sum(len(b.get("tweets", [])) for b in x_items),
            "podcastEpisodes": len(podcast_items),
            "blogPosts": len(blog_items),
            "feedGeneratedAt": (
                (feed_x or {}).get("generatedAt")
                or (feed_podcasts or {}).get("generatedAt")
                or None
            ),
        },
        "errors": errors if errors else None,
    }
