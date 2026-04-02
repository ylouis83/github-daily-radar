from __future__ import annotations

from collections import defaultdict
from math import log1p

from github_daily_radar.models import Candidate


KIND_ORDER = ["project", "skill", "discussion", "other"]
KIND_LABELS_A = {
    "project": "必看项目",
    "skill": "必看技能",
    "discussion": "必看提案 / 讨论",
    "other": "其他",
}
KIND_LABELS_B = {
    "project": "项目补充",
    "skill": "技能补充",
    "discussion": "提案 / 讨论补充",
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
    if candidate.kind == "skill":
        return "这是一个可复用的技能 / 规则包，适合判断是否加入你的技能库。"
    if candidate.kind == "discussion":
        return "这是一个值得关注的提案 / 讨论，适合先看标题和上下文。"
    if candidate.kind in {"issue", "pr"}:
        return "这是一个和功能演进相关的 issue / PR，适合先看是否有新方案。"
    return "这是一个近期活跃的项目，建议先看 README 和最近更新。"


def _fallback_why_now(candidate: Candidate) -> str:
    metrics = candidate.metrics
    if candidate.kind == "skill":
        if metrics.stars or metrics.forks:
            return f"最近有 {metrics.stars} 星 / {metrics.forks} 个 fork，值得快速判断是否纳入技能库。"
        return "这是一个有复用价值的能力包，适合先扫一眼内容结构。"
    if candidate.kind == "discussion":
        if metrics.comments:
            return f"已经有 {metrics.comments} 条评论，说明讨论热度不低。"
        return "属于高信号仓库里的提案 / 讨论，适合优先查看。"
    if candidate.kind in {"issue", "pr"}:
        if metrics.comments:
            return f"已有 {metrics.comments} 条评论，说明这个方案已经有人在认真讨论。"
        return "这是一个可能影响路线图的 issue / PR，适合优先检查。"
    if metrics.stars or metrics.forks:
        return f"最近有 {metrics.stars} 星 / {metrics.forks} 个 fork，说明项目正在被关注。"
    return "这个项目值得先看最近更新和 README，判断是否继续跟踪。"


def _fallback_follow_up(candidate: Candidate) -> str:
    if candidate.kind == "skill":
        return "建议先看示例和使用说明，再决定是否纳入技能库。"
    if candidate.kind == "discussion":
        return "建议先看原帖与评论，再决定是否继续跟进。"
    if candidate.kind in {"issue", "pr"}:
        return "建议先看上下文和关联链接，再判断是否值得跟进。"
    return "建议先看 README、最近提交和 release，再判断是否继续跟踪。"


def _bucket_for_kind(kind: str) -> str:
    if kind == "project":
        return "project"
    if kind == "skill":
        return "skill"
    if kind in {"discussion", "issue", "pr"}:
        return "discussion"
    return "other"


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
            "why_now": _fallback_why_now(candidate),
            "follow_up": _fallback_follow_up(candidate),
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
            item["why_now"] = editorial_item.get("why_now") or item["why_now"]
            item["follow_up"] = editorial_item.get("follow_up") or item["follow_up"]
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


def _overview_lines(items: list[dict], *, variant: str, metadata: dict | None = None) -> list[str]:
    by_bucket = defaultdict(int)
    for item in items:
        by_bucket[_bucket_for_kind(item.get("kind", "other"))] += 1

    lines = [
        f"本卡共 {len(items)} 条，覆盖 {by_bucket['project']} 个项目、{by_bucket['skill']} 个技能、{by_bucket['discussion']} 个提案 / 讨论。",
        "已按编辑优先级排序，并做了同仓库去重，避免单一仓库刷屏。",
    ]
    if metadata:
        parts: list[str] = []
        count = metadata.get("count")
        editorial = metadata.get("editorial")
        a_count = metadata.get("a_count")
        b_count = metadata.get("b_count")
        api_usage = metadata.get("api_usage") or {}
        if count is not None:
            parts.append(f"候选 {count} 条")
        if editorial is not None:
            parts.append(f"LLM 精编 {editorial} 条")
        if a_count is not None and b_count is not None:
            parts.append(f"A {a_count} / B {b_count}")
        if api_usage:
            search_used = api_usage.get("search_used")
            graphql_used = api_usage.get("graphql_used")
            if search_used is not None or graphql_used is not None:
                parts.append(f"API 搜索 {search_used} 次 / GraphQL {graphql_used} 点")
        if parts:
            lines.append("，".join(parts) + "。")
    lines.append("这一卡优先展示今天最值得点开的内容。" if variant == "A" else "这部分是补充阅读，适合扫尾，不会把主卡撑乱。")
    return lines


def build_card_sections(items: list[dict], *, variant: str, metadata: dict | None = None) -> list[dict]:
    kind_labels = KIND_LABELS_A if variant == "A" else KIND_LABELS_B
    overview_title = "今日概览" if variant == "A" else "更多值得扫一眼"
    sections: list[dict] = [{"title": overview_title, "lines": _overview_lines(items, variant=variant, metadata=metadata)}]
    sections.extend(group_digest_items(items, kind_labels=kind_labels))
    return sections


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
        grouped[_bucket_for_kind(item.get("kind", "other"))].append(item)

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
