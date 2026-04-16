from __future__ import annotations

import re
from collections import defaultdict

from github_daily_radar.collectors.buzzing import SOURCE_LABELS
from github_daily_radar.models import BuilderSignal, DailyBrief, ExternalTechCandidate

_GITHUB_REPO_PATTERN = re.compile(r"github\.com/([^/\s]+/[^/\s#?]+)")
_TITLE_REPO_PATTERN = re.compile(r"\b([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\b")

_BUILDER_SECTION_LIMITS = {
    "x": 3,
    "podcast": 2,
    "blog": 2,
}


def _extract_repo_full_name(*, title: str, url: str) -> str | None:
    url_match = _GITHUB_REPO_PATTERN.search(url)
    if url_match:
        return url_match.group(1)
    title_match = _TITLE_REPO_PATTERN.search(title)
    if title_match:
        return title_match.group(1)
    return None


def _tech_why_now(candidate: ExternalTechCandidate) -> str:
    if candidate.comments > 0 and candidate.score > 0:
        return f"{SOURCE_LABELS.get(candidate.source, candidate.source)} 热度高 · {candidate.score} 热度 / {candidate.comments} 评论"
    if candidate.score > 0:
        return f"{SOURCE_LABELS.get(candidate.source, candidate.source)} 热度高 · {candidate.score} 热度"
    return candidate.summary or f"{SOURCE_LABELS.get(candidate.source, candidate.source)} 值得一看"


def extract_builder_signals(feed_data: dict) -> list[BuilderSignal]:
    signals: list[BuilderSignal] = []

    for builder in feed_data.get("x", []):
        tweets = [tweet for tweet in builder.get("tweets", []) if isinstance(tweet, dict) and tweet.get("url")]
        if not tweets:
            continue
        best_tweet = max(
            tweets,
            key=lambda tweet: int(tweet.get("likes", 0)) + int(tweet.get("retweets", 0)) + int(tweet.get("replies", 0)),
        )
        score = int(best_tweet.get("likes", 0)) + int(best_tweet.get("retweets", 0)) + int(best_tweet.get("replies", 0))
        signals.append(
            BuilderSignal(
                source="x",
                section="x",
                title=str(builder.get("name") or builder.get("handle") or "Builder").strip(),
                url=str(best_tweet.get("url")).strip(),
                creator=str(builder.get("name") or builder.get("handle") or "Builder").strip(),
                summary=str(best_tweet.get("text") or "").strip(),
                score=score,
                published_at=str(best_tweet.get("createdAt") or "").strip(),
            )
        )

    for podcast in feed_data.get("podcasts", []):
        url = str(podcast.get("url") or "").strip()
        if not url:
            continue
        signals.append(
            BuilderSignal(
                source="podcast",
                section="podcast",
                title=str(podcast.get("title") or podcast.get("name") or "Podcast").strip(),
                url=url,
                creator=str(podcast.get("name") or "Podcast").strip(),
                summary=str(podcast.get("transcript") or "").strip()[:220],
                score=0,
                published_at=str(podcast.get("publishedAt") or "").strip(),
            )
        )

    for blog in feed_data.get("blogs", []):
        url = str(blog.get("url") or "").strip()
        if not url:
            continue
        signals.append(
            BuilderSignal(
                source="blog",
                section="blog",
                title=str(blog.get("title") or blog.get("name") or "Blog").strip(),
                url=url,
                creator=str(blog.get("name") or blog.get("author") or "Blog").strip(),
                summary=str(blog.get("description") or blog.get("content") or "").strip()[:220],
                score=0,
                published_at=str(blog.get("publishedAt") or "").strip(),
            )
        )

    return signals


def assemble_daily_brief(
    *,
    github_items: list[dict],
    tech_candidates: list[ExternalTechCandidate],
    builder_signals: list[BuilderSignal],
    metadata: dict | None = None,
) -> DailyBrief:
    github_radar = [dict(item) for item in github_items]
    github_by_repo = {
        item.get("repo_full_name"): item
        for item in github_radar
        if isinstance(item.get("repo_full_name"), str) and item.get("repo_full_name")
    }
    tech_pulse: list[dict] = []
    coverage_notes: list[str] = []

    for candidate in sorted(tech_candidates, key=lambda item: (item.score, item.comments), reverse=True):
        repo_full_name = _extract_repo_full_name(title=candidate.title, url=candidate.url)
        github_item = github_by_repo.get(repo_full_name or "")
        if github_item is not None:
            existing_heat = github_item.get("external_heat") or {}
            if candidate.score >= int(existing_heat.get("score", 0)):
                github_item["external_heat"] = {
                    "source": candidate.source,
                    "source_label": SOURCE_LABELS.get(candidate.source, candidate.source),
                    "score": candidate.score,
                    "comments": candidate.comments,
                    "tags": candidate.tags,
                }
            continue

        tech_pulse.append(
            {
                "title": candidate.title,
                "url": candidate.url,
                "summary": candidate.summary,
                "why_now": _tech_why_now(candidate),
                "source": candidate.source,
                "source_label": SOURCE_LABELS.get(candidate.source, candidate.source),
                "score": candidate.score,
                "comments": candidate.comments,
                "tags": list(candidate.tags),
                "published_at": candidate.published_at,
            }
        )

    builder_grouped: dict[str, list[dict]] = defaultdict(list)
    for signal in sorted(builder_signals, key=lambda item: item.score, reverse=True):
        builder_grouped[signal.section].append(
            {
                "title": signal.title,
                "url": signal.url,
                "creator": signal.creator,
                "summary": signal.summary,
                "why_now": signal.summary or signal.creator,
                "score": signal.score,
                "published_at": signal.published_at,
                "source": signal.source,
            }
        )

    builder_watch = {
        section: items[: _BUILDER_SECTION_LIMITS.get(section, 2)]
        for section, items in builder_grouped.items()
        if items
    }

    meta = dict(metadata or {})
    coverage_note = meta.get("coverage_note")
    if isinstance(coverage_note, str) and coverage_note.strip():
        coverage_notes.append(coverage_note.strip())
    stats = {
        **meta,
        "github_count": len(github_radar),
        "tech_pulse_count": len(tech_pulse),
        "builder_count": sum(len(items) for items in builder_watch.values()),
    }

    return DailyBrief(
        github_radar=github_radar,
        tech_pulse=tech_pulse,
        builder_watch=builder_watch,
        stats=stats,
        coverage_notes=coverage_notes,
    )
