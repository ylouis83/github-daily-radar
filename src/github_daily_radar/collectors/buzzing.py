from __future__ import annotations

from collections.abc import Iterable

import httpx

from github_daily_radar.models import ExternalTechCandidate

DEFAULT_BUZZING_FEEDS = {
    "showhn": "https://showhn.buzzing.cc/feed.json",
    "producthunt": "https://ph.buzzing.cc/feed.json",
    "hn": "https://hn.buzzing.cc/feed.json",
    "devto": "https://dev.buzzing.cc/feed.json",
}

SOURCE_LABELS = {
    "showhn": "Show HN",
    "producthunt": "Product Hunt",
    "hn": "Hacker News",
    "devto": "Dev.to",
}

_TECH_TAG_KEYWORDS = {
    "ai",
    "artificial intelligence",
    "developer tools",
    "open source",
    "github",
    "programming",
    "productivity",
    "tech",
}

_TECH_TEXT_KEYWORDS = (
    "ai",
    "agent",
    "builder",
    "claude",
    "code",
    "coding",
    "developer",
    "devtool",
    "github",
    "llm",
    "mcp",
    "open source",
    "product hunt",
    "show hn",
    "tool",
    "workflow",
)


def _iter_tags(item: dict) -> Iterable[str]:
    for tag in item.get("tags", []):
        if isinstance(tag, str) and tag.strip():
            yield tag.strip().lower()


def _is_relevant_item(item: dict) -> bool:
    tag_set = set(_iter_tags(item))
    if tag_set & _TECH_TAG_KEYWORDS:
        return True

    blob = " ".join(
        part
        for part in (
            item.get("title", ""),
            item.get("summary", ""),
            item.get("content_text", ""),
        )
        if isinstance(part, str) and part.strip()
    ).lower()
    return any(keyword in blob for keyword in _TECH_TEXT_KEYWORDS)


def parse_buzzing_feed(feed: dict, *, source: str) -> list[ExternalTechCandidate]:
    items: list[ExternalTechCandidate] = []
    for raw in feed.get("items", []):
        if not isinstance(raw, dict) or not _is_relevant_item(raw):
            continue
        title = str(raw.get("title") or "").strip()
        url = str(raw.get("url") or raw.get("id") or "").strip()
        published_at = str(raw.get("date_published") or raw.get("date_modified") or "").strip()
        if not title or not url or not published_at:
            continue
        items.append(
            ExternalTechCandidate(
                source=source,
                title=title,
                url=url,
                summary=str(raw.get("summary") or raw.get("content_text") or "").strip(),
                score=int(raw.get("_score") or 0),
                comments=int(raw.get("_num_comments") or 0),
                tags=[tag for tag in raw.get("tags", []) if isinstance(tag, str) and tag.strip()],
                published_at=published_at,
            )
        )
    return sorted(items, key=lambda item: (item.score, item.comments), reverse=True)


class BuzzingCollector:
    name = "buzzing"

    def __init__(self, feeds: dict[str, str] | None = None, *, timeout: float = 20.0) -> None:
        self.feeds = feeds or DEFAULT_BUZZING_FEEDS
        self.timeout = timeout

    def collect(self) -> list[ExternalTechCandidate]:
        collected: list[ExternalTechCandidate] = []
        seen_urls: set[str] = set()
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            for source, url in self.feeds.items():
                try:
                    response = client.get(url)
                    response.raise_for_status()
                except Exception:
                    continue
                for item in parse_buzzing_feed(response.json(), source=source):
                    if item.url in seen_urls:
                        continue
                    seen_urls.add(item.url)
                    collected.append(item)
        return sorted(collected, key=lambda item: (item.score, item.comments), reverse=True)
