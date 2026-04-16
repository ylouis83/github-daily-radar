from __future__ import annotations

from collections import defaultdict
from math import log1p

from github_daily_radar.models import Candidate
from github_daily_radar.scoring.dedupe import classify_theme_key


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
PROFILE_LABELS = {
    "project": {"trait": "特点", "capability": "核心能力", "necessity": "引入必要性"},
    "skill": {"trait": "特点", "capability": "核心能力", "necessity": "纳入必要性"},
    "discussion": {"trait": "焦点", "capability": "核心观点", "necessity": "跟进必要性"},
    "issue": {"trait": "焦点", "capability": "核心观点", "necessity": "跟进必要性"},
    "pr": {"trait": "焦点", "capability": "核心观点", "necessity": "跟进必要性"},
    "other": {"trait": "特点", "capability": "核心能力", "necessity": "引入必要性"},
}

_FOCUS_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (("claude-code", "claude code"), "围绕 Claude Code 的终端工作流"),
    (("learn-claude-code", "claude-howto", "howto"), "面向 Claude Code 的上手与实践"),
    (("oh-my-claudecode",), "围绕 Claude Code 的个性化工作台"),
    (("oh-my-codex", "codex"), "围绕 Codex 的开发流程"),
    (("mcp", "model context protocol"), "聚焦 MCP 工具接入与编排"),
    (("browser-use", "browser use", "browser"), "面向浏览器自动化"),
    (("prompt", "prompts"), "围绕 prompt 复用与组织"),
    (("agent", "agents"), "偏 Agent 编排"),
    (("workflow",), "强调工作流自动化"),
    (("rag", "graphrag"), "聚焦 RAG 检索增强"),
    (("vllm", "llama.cpp", "inference"), "聚焦模型推理与部署"),
    (("dify",), "面向应用编排平台"),
    (("open-webui",), "面向本地大模型 UI 与插件生态"),
    (("copilot",), "面向 Copilot / IDE 工作流"),
    (("skill", "skills"), "围绕可复用 skill 资产"),
    (("rule", "rules"), "围绕规则驱动的工作流"),
]


def score_candidate(candidate: Candidate) -> float:
    metrics = candidate.metrics
    if candidate.kind == "skill":
        return (
            log1p(metrics.star_growth_7d) * 6.0
            + log1p(metrics.stars) * 1.2
            + log1p(metrics.forks) * 0.3
            + log1p(metrics.comments + metrics.reactions) * 0.2
        )
    return (
        log1p(metrics.stars) * 0.6
        + log1p(metrics.forks) * 0.3
        + log1p(metrics.comments + metrics.reactions) * 0.5
    )


def _fallback_summary(candidate: Candidate) -> str:
    """优先保留中文真实描述，英文兜底改成结构化中文画像。"""
    return _fallback_profile(candidate)


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


def _prefer_chinese_text(fallback: str, text: str | None) -> str:
    """LLM 文本若不是中文句子，就回退到本地中文模板。"""
    cleaned = (text or "").strip()
    if cleaned and _has_cjk(cleaned):
        return cleaned
    return fallback


def _candidate_text_blob(candidate: Candidate) -> str:
    raw_signals = candidate.raw_signals or {}
    code_item = raw_signals.get("code_search_item") or {}
    repo_item = raw_signals.get("search_item") or {}
    graphql_item = raw_signals.get("graphql_item") or {}
    parts = [
        candidate.title,
        candidate.repo_full_name,
        candidate.body_excerpt,
        candidate.source_query,
        " ".join(candidate.topics),
        " ".join(candidate.labels),
        code_item.get("name", ""),
        code_item.get("path", ""),
        repo_item.get("description", ""),
        repo_item.get("name", ""),
        graphql_item.get("description", ""),
    ]
    return " ".join(part for part in parts if isinstance(part, str) and part.strip()).lower()


def _theme_key_from_candidate(candidate: Candidate) -> str:
    raw_signals = candidate.raw_signals or {}
    code_item = raw_signals.get("code_search_item") or {}
    repo_item = raw_signals.get("search_item") or {}
    graphql_item = raw_signals.get("graphql_item") or {}
    extra_text = " ".join(
        part
        for part in (
            code_item.get("name", ""),
            code_item.get("path", ""),
            repo_item.get("description", ""),
            repo_item.get("name", ""),
            graphql_item.get("description", ""),
        )
        if isinstance(part, str) and part.strip()
    )
    return classify_theme_key(
        title=candidate.title,
        repo_full_name=candidate.repo_full_name,
        body_excerpt=candidate.body_excerpt,
        source_query=candidate.source_query,
        topics=candidate.topics,
        labels=candidate.labels,
        kind=candidate.kind,
        extra_text=extra_text,
    )


def _theme_key_from_item(item: dict) -> str:
    extra_text = " ".join(
        part
        for part in (
            item.get("trait", ""),
            item.get("capability", ""),
            item.get("necessity", ""),
            item.get("summary", ""),
            item.get("why_now", ""),
        )
        if isinstance(part, str) and part.strip()
    )
    topics = [str(topic) for topic in item.get("topics", []) if isinstance(topic, str) and topic.strip()]
    labels = [str(label) for label in item.get("labels", []) if isinstance(label, str) and label.strip()]
    return classify_theme_key(
        title=str(item.get("title") or ""),
        repo_full_name=str(item.get("repo_full_name") or ""),
        body_excerpt=str(item.get("summary") or item.get("why_now") or ""),
        source_query=str(item.get("source_query") or ""),
        topics=topics,
        labels=labels,
        kind=str(item.get("kind") or "other"),
        extra_text=extra_text,
    )


def _focus_phrase(candidate: Candidate) -> str:
    blob = _candidate_text_blob(candidate)
    for needles, phrase in _FOCUS_PATTERNS:
        if any(needle in blob for needle in needles):
            return phrase
    if candidate.source_query.startswith("ossinsight:"):
        if candidate.metrics.star_growth_7d >= 1000:
            return "热度爆发的 AI 相关项目"
        if candidate.metrics.star_growth_7d >= 300:
            return "近期升温的 AI 相关项目"
        return "近期值得关注的 AI 相关项目"
    if candidate.kind == "skill":
        return "围绕可复用能力包的技能资源"
    if candidate.kind in {"discussion", "issue", "pr"}:
        return "围绕方案取舍的讨论条目"
    return "围绕 AI 工具链的项目"


def _fallback_trait(candidate: Candidate) -> str:
    focus = _focus_phrase(candidate)
    m = candidate.metrics
    if candidate.source_query.startswith("ossinsight:"):
        if m.star_growth_7d >= 1000:
            return f"{focus}，当前增量非常高"
        if m.star_growth_7d >= 300:
            return f"{focus}，热度正在持续上升"
        return focus
    # 优先用仓库真实 description，但只接受中文/中英混合中有明显中文的文本
    desc = (candidate.body_excerpt or "").strip()
    if desc and len(desc) >= 8 and not desc.startswith("http") and _has_cjk(desc):
        # 截断到合理长度，避免英文原文直接泄露
        return _truncate(desc, 42)
    if candidate.kind == "skill":
        if m.stars >= 500:
            return f"{focus}，⭐{m.stars} 社区广泛验证"
        if m.stars >= 100:
            return f"{focus}，社区验证较强"
        return focus
    if candidate.kind in {"discussion", "issue", "pr"}:
        if m.comments >= 20:
            return f"{focus}，讨论已进入收敛阶段"
        return f"{focus}，适合先看争议点"
    if candidate.metrics.has_new_release:
        return f"{focus}，近期刚有新 release"
    if m.stars >= 100:
        return f"{focus}，已形成一定社区热度"
    return focus


def _fallback_capability(candidate: Candidate) -> str:
    # 优先用 topics 差异化
    topics = [t for t in candidate.topics[:4] if t and len(t) > 1]
    if topics:
        return f"涉及 {' / '.join(topics)}，封装为可接入的能力层。"
    blob = _candidate_text_blob(candidate)
    if any(needle in blob for needle in ("mcp", "tool")):
        return "把外部工具和能力封装成更容易接入的调用层。"
    if "browser" in blob:
        return "把浏览器操作自动化成可编排的动作流。"
    if any(needle in blob for needle in ("prompt", "rules", "skill")):
        return "把可复用的提示词和规则沉淀成可执行资产。"
    if any(needle in blob for needle in ("agent", "workflow")):
        return "把复杂任务拆成可调度、可复用的 Agent 流程。"
    if any(needle in blob for needle in ("rag", "retrieval", "search")):
        return "把检索与生成串成更容易落地的问答或分析流程。"
    if any(needle in blob for needle in ("inference", "vllm", "llama.cpp")):
        return "把模型推理和部署做成更容易落地的基础设施。"
    if candidate.kind == "discussion":
        return "把方案争议、取舍和结论整理成可跟进的判断依据。"
    if candidate.kind == "skill":
        return "把这类能力打包成可以直接复用的工作流。"
    return "把相关 AI 能力包装成更容易试用和复用的工作流。"


def _fallback_necessity(candidate: Candidate) -> str:
    m = candidate.metrics
    if candidate.source_query.startswith("ossinsight:"):
        if m.star_growth_7d >= 1000:
            return "已经出现明显爆发，适合优先判断是否值得跟进。"
        if m.star_growth_7d >= 300:
            return "热度正在上升，适合趁势先看是否值得收录。"
        return "热度已在抬升，适合快速判断是否值得关注。"
    # 数据驱动差异化
    if m.star_growth_7d >= 500:
        return f"近期暴涨 +{m.star_growth_7d}⭐，建议立即关注。"
    if m.star_growth_7d >= 100:
        return f"增长 +{m.star_growth_7d}⭐，值得优先跟进。"
    if m.forks >= 50:
        return f"已被 {m.forks} 人 fork，复用价值明确。"
    if m.stars >= 1000:
        return f"⭐{m.stars} 广泛验证，可作为参考标杆。"
    if m.stars >= 500:
        return f"⭐{m.stars} 社区验证充分，值得深入评估。"
    if candidate.kind in {"discussion", "issue", "pr"}:
        if m.comments >= 20:
            return "如果你关注方案走向，这类讨论值得跟进结论。"
        return "如果你想提前判断方案方向，这类讨论值得先浏览。"
    if candidate.metrics.has_new_release:
        return "已有新版本信号，适合判断是否需要接入或替换。"
    if m.stars >= 100:
        return f"⭐{m.stars} 已有社区验证，适合判断是否值得引入。"
    return "形态清晰，适合先观察后续发展。"


def _compose_profile(kind: str, trait: str, capability: str, necessity: str) -> str:
    labels = PROFILE_LABELS.get(kind, PROFILE_LABELS["other"])
    parts = []
    if trait:
        parts.append(f"{labels['trait']}：{_truncate(trait, 42)}")
    if capability:
        parts.append(f"{labels['capability']}：{_truncate(capability, 48)}")
    if necessity:
        parts.append(f"{labels['necessity']}：{_truncate(necessity, 48)}")
    return " · ".join(parts)


def _fallback_profile(candidate: Candidate) -> str:
    return _compose_profile(
        candidate.kind,
        _fallback_trait(candidate),
        _fallback_capability(candidate),
        _fallback_necessity(candidate),
    )


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
        fallback_trait = _fallback_trait(candidate)
        fallback_capability = _fallback_capability(candidate)
        fallback_necessity = _fallback_necessity(candidate)
        fallback_summary = _compose_profile(candidate.kind, fallback_trait, fallback_capability, fallback_necessity)
        fallback_why_now = _fallback_why_now(candidate)
        item = {
            "candidate_id": candidate.candidate_id,
            "kind": candidate.kind,
            "title": candidate.title,
            "url": candidate.url,
            "trait": fallback_trait,
            "capability": fallback_capability,
            "necessity": fallback_necessity,
            "summary": fallback_summary,
            "why_now": fallback_why_now,
            "editorial_rank": None,
            "section": None,
            "repo_full_name": candidate.repo_full_name,
            "source_query": candidate.source_query,
            "theme": _theme_key_from_candidate(candidate),
            "metrics": candidate.metrics.model_dump(),
            "rule_scores": dict(candidate.rule_scores),
            "score": score_candidate(candidate),
            # star 相关字段供 feishu 卡片渲染 badge
            "stars": candidate.metrics.stars,
            # OSSInsight past_week 返回的是 7 天增量，不应当作 1 天增量
            "star_delta_1d": (
                candidate.metrics.star_growth_7d
                if not candidate.source_query.startswith("ossinsight:trending:past_week")
                else candidate.metrics.star_growth_7d // 7
            ),
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
            has_profile_fields = any(
                editorial_item.get(field)
                for field in ("trait", "characteristic", "capability", "core_capability", "necessity", "necessity_assessment")
            )
            if has_profile_fields:
                item["trait"] = _prefer_chinese_text(
                    item["trait"],
                    editorial_item.get("trait") or editorial_item.get("characteristic"),
                )
                item["capability"] = _prefer_chinese_text(
                    item["capability"],
                    editorial_item.get("capability") or editorial_item.get("core_capability"),
                )
                item["necessity"] = _prefer_chinese_text(
                    item["necessity"],
                    editorial_item.get("necessity") or editorial_item.get("necessity_assessment"),
                )
                item["summary"] = _compose_profile(
                    item["kind"],
                    item["trait"],
                    item["capability"],
                    item["necessity"],
                )
            else:
                item["summary"] = _prefer_chinese_text(item["summary"], editorial_item.get("summary"))
            item["why_now"] = _prefer_chinese_text(item["why_now"], editorial_item.get("why_now"))
            rank = editorial_item.get("rank", editorial_item.get("editorial_rank"))
            if rank is not None:
                item["editorial_rank"] = rank
            if editorial_item.get("section"):
                item["section"] = editorial_item["section"]
        items.append(item)
    return items


def choose_daily_limit(
    items: list[dict],
    *,
    min_items: int = 10,
    max_items: int = 20,
) -> int:
    total = len(items)
    if total <= 0:
        return 0
    if total <= min_items:
        return total

    ordered = sorted(items, key=_selection_sort_key)
    quality_window = ordered[: min(total, max_items)]
    quality_cutoff = _quality_value(quality_window[min(len(quality_window), min_items) - 1])
    quality_floor = max(2.0, quality_cutoff * 0.8)
    strong_count = sum(1 for item in quality_window if _quality_value(item) >= quality_floor)
    return min(total, max_items, max(min_items, strong_count))


def select_top_items(
    items: list[dict],
    *,
    min_items: int = 10,
    max_items: int = 20,
    per_repo_cap: int = 1,
    project_first: bool = True,
    blocked_themes: set[str] | None = None,
) -> list[dict]:
    """从候选中选出项目优先的单卡列表，按编辑 rank → 分数排序，同仓库去重。"""

    target_limit = choose_daily_limit(items, min_items=min_items, max_items=max_items)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        grouped[_bucket_for_kind(item.get("kind", "other"))].append(item)

    for kind in grouped:
        grouped[kind] = sorted(
            grouped[kind],
            key=lambda item: _selection_sort_key(item, blocked_themes=blocked_themes),
        )

    selected: list[dict] = []
    repo_counts: dict[str, int] = defaultdict(int)
    cycle_order = _selection_cycle(project_first=project_first)

    while len(selected) < target_limit:
        progressed = False
        for kind in cycle_order:
            if len(selected) >= target_limit:
                break
            item = _take_next_bucket_item(grouped.get(kind, []), repo_counts=repo_counts, per_repo_cap=per_repo_cap)
            if item is None:
                continue
            selected.append(item)
            progressed = True
        if not progressed:
            break

    return selected


def _selection_sort_key(item: dict, *, blocked_themes: set[str] | None = None) -> tuple[int, int, int, float, str]:
    theme = item.get("theme") or _theme_key_from_item(item)
    blocked_flag = 1 if blocked_themes and theme in blocked_themes else 0
    rank = item.get("editorial_rank")
    rank_key = int(rank) if rank is not None else 10_000
    score = float(item.get("score") or 0.0)
    return (blocked_flag, 0 if rank is not None else 1, rank_key, -score, item.get("title", ""))


def _quality_value(item: dict) -> float:
    score = float(item.get("score") or 0.0)
    rank = item.get("editorial_rank")
    if rank is None:
        return score
    try:
        rank_value = int(rank)
    except (TypeError, ValueError):
        return score
    return score + max(0.0, 2.0 - 0.2 * max(rank_value - 1, 0))


def _selection_cycle(*, project_first: bool) -> list[str]:
    if project_first:
        return ["project", "project", "skill", "discussion", "other"]
    return ["skill", "discussion", "project", "other"]


def _take_next_bucket_item(items: list[dict], *, repo_counts: dict[str, int], per_repo_cap: int) -> dict | None:
    while items:
        item = items.pop(0)
        repo_key = item.get("repo_full_name") or item.get("url") or item.get("title")
        if repo_counts[repo_key] >= per_repo_cap:
            continue
        repo_counts[repo_key] += 1
        return item
    return None



def _overview_lines(items: list[dict], *, variant: str, metadata: dict | None = None) -> list[str]:
    by_bucket = defaultdict(int)
    for item in items:
        by_bucket[_bucket_for_kind(item.get("kind", "other"))] += 1

    lines = [
        f"本卡共 {len(items)} 条，覆盖 {by_bucket['project']} 个项目、{by_bucket['skill']} 个技能、{by_bucket['discussion']} 个提案 / 讨论。",
        "已按编辑优先级排序，并做了同仓库去重，避免单一仓库刷屏。",
    ]
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
