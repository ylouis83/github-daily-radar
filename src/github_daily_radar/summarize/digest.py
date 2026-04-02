from __future__ import annotations

from collections import defaultdict
from math import log1p

from github_daily_radar.models import Candidate


KIND_ORDER = ["project", "skill", "discussion", "issue", "pr", "other"]
KIND_LABELS_A = {
    "project": "必看项目",
    "skill": "必看技能",
    "discussion": "必看提案 / 讨论",
    "issue": "必看提案 / 讨论",
    "pr": "必看提案 / 讨论",
    "other": "其他",
}
KIND_LABELS_B = {
    "project": "项目补充",
    "skill": "技能补充",
    "discussion": "提案 / 讨论补充",
    "issue": "提案 / 讨论补充",
    "pr": "提案 / 讨论补充",
    "other": "其他",
}


def score_candidate(candidate: Candidate) -> float:
    metrics = candidate.metrics
    return (
        log1p(metrics.stars) * 0.6
        + log1p(metrics.forks) * 0.3
        + log1p(metrics.comments + metrics.reactions) * 0.5
    )


def _fallback_summary(candidate: Candidate) -> str:
    if candidate.body_excerpt:
        return candidate.body_excerpt.strip()[:120]
    return f"信号: ⭐{candidate.metrics.stars}  🍴{candidate.metrics.forks}  💬{candidate.metrics.comments}"


def build_display_items(candidates: list[Candidate], editorial: list[dict]) -> list[dict]:
    editorial_by_url = {item.get("url"): item for item in editorial if item.get("url")}
    editorial_by_title = {item.get("title"): item for item in editorial if item.get("title")}

    items: list[dict] = []
    for candidate in candidates:
        item = {
            "kind": candidate.kind,
            "title": candidate.title,
            "url": candidate.url,
            "summary": _fallback_summary(candidate),
            "why_now": None,
            "editorial_rank": None,
            "section": None,
            "repo_full_name": candidate.repo_full_name,
            "score": score_candidate(candidate),
        }
        editorial_item = editorial_by_url.get(candidate.url) or editorial_by_title.get(candidate.title)
        if editorial_item:
            item["kind"] = editorial_item.get("kind", item["kind"])
            item["title"] = editorial_item.get("title", item["title"])
            item["url"] = editorial_item.get("url", item["url"])
            item["summary"] = editorial_item.get("summary") or item["summary"]
            item["why_now"] = editorial_item.get("why_now")
            rank = editorial_item.get("rank", editorial_item.get("editorial_rank"))
            if rank is not None:
                item["editorial_rank"] = rank
            if editorial_item.get("section"):
                item["section"] = editorial_item["section"]
        items.append(item)
    return items


def split_a_b(
    items: list[dict],
    *,
    a_min: int = 8,
    a_max: int = 12,
    b_min: int = 8,
    b_max: int = 12,
    per_repo_cap_a: int = 1,
) -> tuple[list[dict], list[dict]]:
    def sort_key(item: dict) -> tuple[int, int, float, str]:
        rank = item.get("editorial_rank")
        rank_key = int(rank) if rank is not None else 10_000
        score = float(item.get("score") or 0.0)
        return (0 if rank is not None else 1, rank_key, -score, item.get("title", ""))

    ordered = sorted(items, key=sort_key)
    a_items: list[dict] = []
    repo_counts: dict[str, int] = defaultdict(int)
    for item in ordered:
        if len(a_items) >= a_max:
            break
        repo_key = item.get("repo_full_name") or item.get("url") or item.get("title")
        if repo_counts[repo_key] >= per_repo_cap_a:
            continue
        a_items.append(item)
        repo_counts[repo_key] += 1

    if len(a_items) < a_min:
        for item in ordered:
            if item in a_items:
                continue
            if len(a_items) >= a_min:
                break
            a_items.append(item)

    remaining = [item for item in ordered if item not in a_items]
    b_items = remaining[:b_max]
    if len(b_items) < b_min:
        b_items = remaining[:b_min]

    for item in b_items:
        if item.get("summary") and len(item["summary"]) > 80:
            item["summary"] = item["summary"][:80]
    return a_items, b_items


def group_digest_items(
    items: list[dict],
    *,
    kind_labels: dict[str, str] | None = None,
    ordered_kinds: list[str] | None = None,
) -> list[dict]:
    kind_labels = kind_labels or {}
    ordered_kinds = ordered_kinds or KIND_ORDER
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        grouped[item.get("kind", "other")].append(item)

    def sort_key(item: dict) -> tuple[int, int, float, str]:
        rank = item.get("editorial_rank")
        rank_key = int(rank) if rank is not None else 10_000
        score = float(item.get("score") or 0.0)
        return (0 if rank is not None else 1, rank_key, -score, item.get("title", ""))

    sections: list[dict] = []
    for kind in ordered_kinds:
        if kind in grouped:
            title = kind_labels.get(kind, kind.title())
            sections.append({"title": title, "items": sorted(grouped[kind], key=sort_key)})
    return sections
