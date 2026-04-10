"""GitHub Trending page scraper — zero API cost complement to OSSInsight."""

import logging
import re

import httpx

from github_daily_radar.collectors.base import Collector
from github_daily_radar.models import Candidate, CandidateMetrics
from github_daily_radar.normalize.candidates import _utc_now_iso

logger = logging.getLogger(__name__)

# Regex patterns for parsing GitHub Trending HTML
# Repo link: /owner/name
_RE_REPO = re.compile(r'href="/([^/]+/[^/"]+)"[^>]*>\s*\n?\s*(?:<svg[^>]*>.*?</svg>\s*)?([^<]+)</a>', re.DOTALL)
# Star count on the page (e.g. "1,234")
_RE_STARS_TOTAL = re.compile(r'href="/[^"]+/stargazers"[^>]*>\s*(?:<svg[^>]*>.*?</svg>\s*)?([0-9,]+)\s*</a>', re.DOTALL)
# Daily stars badge (e.g. "123 stars today")
_RE_STARS_TODAY = re.compile(r'([0-9,]+)\s+stars?\s+(?:today|this week|this month)', re.IGNORECASE)
# Description
_RE_DESC = re.compile(r'<p class="col-9[^"]*">\s*(.*?)\s*</p>', re.DOTALL)


def _parse_int(text: str) -> int:
    return int(text.replace(",", "").strip()) if text else 0


def parse_trending_html(html: str) -> list[dict]:
    """Parse GitHub Trending page HTML to extract repo info."""
    items: list[dict] = []
    # Split by article tags (each repo is an <article>)
    articles = re.split(r'<article\b[^>]*>', html)
    for article in articles[1:]:  # skip first (before any article)
        repo_match = re.search(r'href="/([^/"]+/[^/"]+)"', article)
        if not repo_match:
            continue
        repo_name = repo_match.group(1).strip()

        desc_match = _RE_DESC.search(article)
        description = desc_match.group(1).strip() if desc_match else ""
        # Clean HTML tags from description
        description = re.sub(r'<[^>]+>', '', description).strip()

        stars_total = 0
        stars_match = re.search(r'href="/[^"]+/stargazers"[^>]*>(.*?)</a>', article, re.DOTALL)
        if stars_match:
            stars_total = _parse_int(re.sub(r'<[^>]+>', '', stars_match.group(1)))

        stars_today = 0
        today_match = _RE_STARS_TODAY.search(article)
        if today_match:
            stars_today = _parse_int(today_match.group(1))

        lang_match = re.search(r'itemprop="programmingLanguage"[^>]*>([^<]+)</span>', article)
        language = lang_match.group(1).strip() if lang_match else ""

        items.append({
            "repo_name": repo_name,
            "description": description,
            "stars": stars_total,
            "stars_today": stars_today,
            "language": language,
        })
    return items


class TrendingCollector(Collector):
    """Scrape github.com/trending for daily hot repos — zero API budget cost."""

    name = "trending"

    DEFAULT_URLS = [
        "https://github.com/trending?since=daily",
        "https://github.com/trending?since=weekly",
        "https://github.com/trending/python?since=daily",
        "https://github.com/trending/typescript?since=daily",
        "https://github.com/trending/go?since=daily",
        "https://github.com/trending/rust?since=daily",
    ]

    def __init__(self, client=None, urls: list[str] | None = None, *, max_items: int = 15) -> None:
        super().__init__(client)
        self.urls = urls or list(self.DEFAULT_URLS)
        self.max_items = max_items

    def collect(self) -> list[Candidate]:
        seen: set[str] = set()
        candidates: list[Candidate] = []

        for url in self.urls:
            try:
                response = httpx.get(url, timeout=15.0, follow_redirects=True, headers={
                    "Accept": "text/html",
                    "User-Agent": "github-daily-radar/1.0",
                })
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("TrendingCollector fetch failed for %s: %s", url, exc)
                continue

            items = parse_trending_html(response.text)
            for item in items:
                repo_name = item["repo_name"]
                if repo_name in seen:
                    continue
                seen.add(repo_name)

                candidate = Candidate(
                    candidate_id=f"trending:{repo_name}",
                    kind="project",
                    source_query=f"github-trending:{url.split('?')[0].split('/')[-1] or 'all'}",
                    title=repo_name,
                    url=f"https://github.com/{repo_name}",
                    repo_full_name=repo_name,
                    author=repo_name.split("/", 1)[0],
                    created_at=_utc_now_iso(),
                    updated_at=_utc_now_iso(),
                    body_excerpt=item.get("description", ""),
                    topics=[item["language"]] if item.get("language") else [],
                    labels=[],
                    metrics=CandidateMetrics(
                        stars=item.get("stars", 0),
                        star_growth_7d=item.get("stars_today", 0),
                    ),
                    raw_signals={"trending_item": item, "trending_url": url},
                    rule_scores={"trending_daily_stars": float(item.get("stars_today", 0))},
                    dedupe_key=repo_name,
                )
                candidates.append(candidate)

                if len(candidates) >= self.max_items:
                    return candidates

        return candidates
