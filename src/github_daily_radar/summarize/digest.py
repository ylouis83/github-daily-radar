from __future__ import annotations

from collections import defaultdict
from collections import deque
from math import log1p

from github_daily_radar.models import Candidate


def _truncate(text: str, max_len: int = 100) -> str:
    """按单词/标点边界截断，不切半个词。"""
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    # 英文按空格截断
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    # 中文按最后一个句号/逗号截断
    for sep in ("。", "，", "、", ". ", ", "):
        pos = cut.rfind(sep)
        if pos > max_len // 2:
            cut = cut[: pos + len(sep)]
            break
    return cut.rstrip() + "…"


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


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
    """优先保留中文真实描述，英文兜底改成中文摘要模板。"""
    if candidate.source_query.startswith("ossinsight:"):
        growth = candidate.metrics.star_growth_7d or candidate.metrics.stars
        if growth >= 1000:
            return "OSSInsight 监测到热度爆发，建议先看趋势、README 和最近 release。"
        if growth >= 300:
            return "OSSInsight 监测到近期热度明显上升，适合先看变更和 release。"
        return "OSSInsight 监测到近期热度上升，建议先看 README 和最近提交。"

    desc = (candidate.body_excerpt or "").strip()
    if desc and _has_cjk(desc):
        return _truncate(desc, 100)

    # 英文或无描述时，用中文模板避免把原文英文直接带进卡片。
    if candidate.kind == "project":
        if candidate.metrics.has_new_release:
            return "这是近期值得关注的仓库，建议先看 README、最近提交和 release。"
        if candidate.metrics.stars >= 100:
            return "这是近期热度很高的仓库，建议先看趋势、README 和最近提交。"
        return "这是一个值得快速浏览的仓库，先看 README 和最近提交。"
    if candidate.kind == "skill":
        if candidate.metrics.stars >= 100:
            return "这是一个可复用度很高的技能资源，适合评估是否纳入技能库。"
        return "这是一个可复用的 skill / prompt / rules 资源，适合评估是否纳入技能库。"
    if candidate.kind in {"discussion", "issue", "pr"}:
        if candidate.metrics.comments >= 20:
            return "这是一个评论活跃的提案或讨论，重点看争议点和结论。"
        return "这是一个值得跟进的提案或讨论，重点看方案、评论和结论。"

    # 再退一步只给信号，不泄露英文原文。
    m = candidate.metrics
    parts = []
    if m.stars:
        parts.append(f"⭐{m.stars}")
    if m.forks:
        parts.append(f"🍴{m.forks}")
    if m.comments:
        parts.append(f"💬{m.comments}")
    return " ".join(parts) if parts else "这是一个值得关注的条目，建议先看标题和原始链接。"


def _fallback_why_now(candidate: Candidate) -> str:
    """简短信号，不超过 1 句。"""
    m = candidate.metrics
    if candidate.source_query.startswith("ossinsight:") and m.stars:
        if m.star_growth_7d >= 1000:
            return f"OSSInsight 热度爆发 · +{m.star_growth_7d}⭐"
        if m.star_growth_7d >= 300:
            return f"OSSInsight 热度上升 · +{m.star_growth_7d}⭐"
        return f"OSSInsight 近期 +{m.stars}⭐"
    if candidate.kind == "project":
        if m.has_new_release:
            return "有新 release"
        if m.star_growth_7d >= 200:
            return f"近 7 天 +{m.star_growth_7d}⭐"
    if m.comments >= 10:
        return f"{m.comments} 条讨论"
    if candidate.kind == "skill":
        if m.stars >= 100:
            return f"可复用 · ⭐{m.stars}"
        if m.forks >= 10:
            return f"适合复用 · 🍴{m.forks}"
    if m.stars >= 100:
        return f"⭐{m.stars}"
    return ""


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
            "candidate_id": candidate.candidate_id,
            "kind": candidate.kind,
            "title": candidate.title,
            "url": candidate.url,
            "summary": _fallback_summary(candidate),
            "why_now": _fallback_why_now(candidate),
            "editorial_rank": None,
            "section": None,
            "repo_full_name": candidate.repo_full_name,
            "source_query": candidate.source_query,
            "metrics": candidate.metrics.model_dump(),
            "rule_scores": dict(candidate.rule_scores),
            "score": score_candidate(candidate),
            # star 相关字段供 feishu 卡片渲染 badge
            "stars": candidate.metrics.stars,
            "star_delta_1d": candidate.metrics.star_growth_7d,
            "star_velocity": (
                "surge" if candidate.metrics.star_growth_7d >= 200
                else "rising" if candidate.metrics.star_growth_7d >= 50
                else ""
            ),
        }
        editorial_item = editorial_by_url.get(candidate.url) or editorial_by_title.get(candidate.title)
        if editorial_item:
            item["kind"] = editorial_item.get("kind", item["kind"])
            item["title"] = editorial_item.get("title", item["title"])
            item["url"] = editorial_item.get("url", item["url"])
            item["summary"] = editorial_item.get("summary") or item["summary"]
            item["why_now"] = editorial_item.get("why_now") or item["why_now"]
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
    bucketed: dict[str, deque[dict]] = {
        kind: deque(item for item in ordered if _bucket_for_kind(item.get("kind", "other")) == kind)
        for kind in KIND_ORDER
    }

    def take_diverse(limit: int, buckets: dict[str, deque[dict]]) -> list[dict]:
        selected: list[dict] = []
        repo_counts: dict[str, int] = defaultdict(int)
        while len(selected) < limit:
            progress = False
            for kind in KIND_ORDER:
                bucket = buckets[kind]
                while bucket:
                    candidate = bucket.popleft()
                    repo_key = candidate.get("repo_full_name") or candidate.get("url") or candidate.get("title")
                    if repo_counts[repo_key] >= per_repo_cap_a:
                        continue
                    selected.append(candidate)
                    repo_counts[repo_key] += 1
                    progress = True
                    break
                if len(selected) >= limit:
                    break
            if not progress:
                break
        return selected

    a_items = take_diverse(a_max, bucketed)
    if len(a_items) < a_min:
        a_items = ordered[:a_min]

    remaining = [item for item in ordered if item not in a_items]
    remaining_buckets: dict[str, deque[dict]] = {
        kind: deque(item for item in remaining if _bucket_for_kind(item.get("kind", "other")) == kind)
        for kind in KIND_ORDER
    }
    b_items = take_diverse(b_max, remaining_buckets)
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
    return build_card_sections_with_label(items, variant=variant, metadata=metadata, bundle_label=None)


def build_card_sections_with_label(
    items: list[dict],
    *,
    variant: str,
    metadata: dict | None = None,
    bundle_label: str | None = None,
) -> list[dict]:
    kind_labels = KIND_LABELS_A if variant == "A" else KIND_LABELS_B
    if bundle_label:
        overview_title = f"{bundle_label} · 今日概览" if variant == "A" else f"{bundle_label} · 更多值得扫一眼"
    else:
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
