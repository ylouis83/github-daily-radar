"""Feishu interactive card rendering and delivery.

Design principles (v3):
  • 单版输出 — 不再分 A/B，一张卡片展示所有精选
  • 四大分区 — 💥 今日爆款 / 🚀 核心 AI 项目 / 🧩 MCP & Skills / 💬 提案与讨论
  • 爆款区 — 仅含 TrendingCollector + OSSInsight 日增 ≥200⭐ 的项目，与核心项目互斥
  • 分层密度 — 精编条目 (前 N 条) 带完整画像；其余紧凑速览
  • column_set 概览面板 — 稳定四列统计
  • 空分区不渲染
"""
from __future__ import annotations

from datetime import date
from collections import Counter, defaultdict
from urllib.parse import urlparse

import httpx

# ── Constants ──────────────────────────────────────────────────────
# GitHub 主榜保留少量完整画像，其余进入速览
FEATURED_LIMIT = 4

SECTION_ICONS = {
    "project": "核心项目",
    "skill": "技能与 MCP",
    "discussion": "讨论与提案",
}

BUILDER_SECTION_LABELS = {
    "x": "X",
    "podcast": "Podcast",
    "blog": "Blog",
}

CARD_SUBTITLE = "GitHub 主榜 · 科技热讯 · Builder Watch"
STYLE_REVIEW_NOTE = "仅预览卡片样式，不加载实时内容"

TRACK_COPY = {
    "github": {
        "title": "GitHub 主榜",
        "subtitle": "开源仓库、技能资产与讨论线索",
        "metric_label": "主榜",
    },
    "tech": {
        "title": "科技热讯",
        "subtitle": "发布动态、工程信号与外部热点",
        "metric_label": "热讯",
    },
    "builder": {
        "title": "Builder Watch",
        "subtitle": "创作者观点、播客与长文解读",
        "metric_label": "观察",
    },
}

TRACK_BADGES = {
    "github": {"label": "主线", "color": "blue"},
    "tech": {"label": "外部", "color": "orange"},
    "builder": {"label": "人物", "color": "green"},
}

# kind → 画像结构化字段标签
PROFILE_LABELS = {
    "project":    {"trait": "定位", "capability": "能力", "necessity": "价值"},
    "skill":      {"trait": "定位", "capability": "能力", "necessity": "价值"},
    "discussion": {"trait": "议题", "capability": "结论", "necessity": "影响"},
    "other":      {"trait": "定位", "capability": "能力", "necessity": "价值"},
}

SOURCE_ICON_TOKENS = {
    "github": "platform_outlined",
    "youtube": "file-link-video_outlined",
    "x": "internet_outlined",
    "web": "internet_outlined",
}

SOURCE_HOME_LINKS = {
    "github": "https://github.com",
    "youtube": "https://www.youtube.com",
    "x": "https://x.com",
}

# star 速度 → text_tag 颜色
_VELOCITY_TAG_COLOR = {
    "explosion": "red",
    "surge": "orange",
    "rising": "blue",
    "new": "green",
}

# ── Helpers ───────────────────────────────────────────────────────

def _truncate_text(text: str, max_len: int = 100) -> str:
    """Prefer truncating at a visible boundary instead of mid-token."""
    cleaned = (text or "").strip()
    if len(cleaned) <= max_len:
        return cleaned
    cut = cleaned[:max_len].rstrip()
    boundary_chars = [" ", "·", "。", "，", "、", ".", ",", ";", "；", ":", "：", "-", "/", "_"]
    boundary = max((cut.rfind(char) for char in boundary_chars), default=-1)
    if boundary >= max_len // 2:
        cut = cut[:boundary].rstrip(" -_/.,;:，。")
    return cut.rstrip() + "…"


def _format_star_badge(item: dict) -> str:
    """格式化 star 徽标：+1161★ 或 12.3K★"""
    delta = item.get("star_delta_1d", 0)

    if delta and delta > 50:
        return f"+{delta}★"

    stars = item.get("stars", 0)
    if stars >= 1000:
        return f"{stars / 1000:.1f}K★"
    elif stars > 0:
        return f"{stars}★"
    return ""


def _format_star_tag(item: dict) -> str:
    """用 text_tag 彩色标签展示 star 增量（仅精编条目）"""
    delta = item.get("star_delta_1d", 0)
    velocity = item.get("star_velocity", "")
    color = _VELOCITY_TAG_COLOR.get(velocity, "neutral")

    if delta and delta > 50:
        return f"<text_tag color='{color}'>+{delta}★</text_tag>"

    stars = item.get("stars", 0)
    if stars >= 1000:
        return f"<text_tag color='neutral'>{stars / 1000:.1f}K★</text_tag>"
    elif stars > 0:
        return f"<text_tag color='neutral'>{stars}★</text_tag>"
    return ""


def _format_external_heat(item: dict) -> str:
    external_heat = item.get("external_heat")
    if not isinstance(external_heat, dict):
        return ""
    source_label = str(external_heat.get("source_label") or external_heat.get("source") or "").strip()
    score = int(external_heat.get("score") or 0)
    if source_label and score > 0:
        return f"{source_label} · {score} 热度"
    if source_label:
        return source_label
    return ""


def _source_key_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "github.com" in host:
        return "github"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "x.com" in host or "twitter.com" in host:
        return "x"
    return "web"


def _escape_link_attr(value: str) -> str:
    return value.replace("'", "%27")


def _format_source_link(*, label: str, url: str, icon_token: str) -> str:
    safe_url = _escape_link_attr(url)
    return f"<link icon='{icon_token}' url='{safe_url}'>{label}</link>"


def _resolve_source_meta(item: dict, *, fallback_label: str | None = None) -> tuple[str, str, str]:
    url = str(item.get("url") or "").strip()
    source_label = str(item.get("source_label") or fallback_label or "").strip()
    source_key = _source_key_from_url(url)

    if source_key == "github":
        return "GitHub", SOURCE_ICON_TOKENS["github"], url
    if source_key == "youtube":
        return "YouTube", SOURCE_ICON_TOKENS["youtube"], url
    if source_key == "x":
        return "X", SOURCE_ICON_TOKENS["x"], url

    lowered_label = source_label.lower()
    if "github" in lowered_label:
        return "GitHub", SOURCE_ICON_TOKENS["github"], url
    if "youtube" in lowered_label:
        return "YouTube", SOURCE_ICON_TOKENS["youtube"], url
    if lowered_label in {"x", "twitter"}:
        return "X", SOURCE_ICON_TOKENS["x"], url
    if source_label:
        return source_label, SOURCE_ICON_TOKENS["web"], url
    return (fallback_label or "Web"), SOURCE_ICON_TOKENS["web"], url


def _render_source_link(item: dict, *, fallback_label: str | None = None) -> str:
    label, icon_token, url = _resolve_source_meta(item, fallback_label=fallback_label)
    if url:
        return _format_source_link(label=label, url=url, icon_token=icon_token)
    return label


def _platform_source_link(source_key: str) -> str | None:
    url = SOURCE_HOME_LINKS.get(source_key)
    icon_token = SOURCE_ICON_TOKENS.get(source_key)
    label = {"github": "GitHub", "youtube": "YouTube", "x": "X"}.get(source_key)
    if not url or not icon_token or not label:
        return None
    return _format_source_link(label=label, url=url, icon_token=icon_token)


def _shared_source_key(items: list[dict]) -> str | None:
    source_keys = {
        _source_key_from_url(str(item.get("url") or "").strip())
        for item in items
        if str(item.get("url") or "").strip()
    }
    if len(source_keys) != 1:
        return None
    source_key = next(iter(source_keys))
    return source_key if source_key in SOURCE_HOME_LINKS else None


def _format_section_heading(
    label: str,
    *,
    count: int | None = None,
    source_key: str | None = None,
) -> str:
    count_suffix = f" · {count}" if count is not None else ""
    heading = f"**{label}{count_suffix}**"
    source_link = _platform_source_link(source_key) if source_key else None
    if source_link:
        return f"{heading}  ·  {source_link}"
    return heading


def _title_mentions_creator(title: str, creator: str) -> bool:
    title_norm = "".join(char for char in title.lower() if char.isalnum() or "\u4e00" <= char <= "\u9fff")
    creator_norm = "".join(char for char in creator.lower() if char.isalnum() or "\u4e00" <= char <= "\u9fff")
    return bool(title_norm and creator_norm and creator_norm in title_norm)


def _build_track_header(*, track_key: str, title: str, subtitle: str, count: int, metric_label: str) -> dict:
    badge = TRACK_BADGES.get(track_key, {"label": "Track", "color": "grey"})
    return {
        "tag": "column_set",
        "flex_mode": "none",
        "horizontal_spacing": "default",
        "columns": [
            {
                "tag": "column",
                "width": "auto",
                "vertical_align": "center",
                "elements": [
                    {
                        "tag": "markdown",
                        "content": (
                            f"**{title}**  "
                            f"<text_tag color='{badge['color']}'>{badge['label']}</text_tag>\n"
                            f"{subtitle}"
                        ),
                    }
                ],
            },
        ],
    }


def _build_metric_column(value: str | int, label: str) -> dict:
    return {
        "tag": "column",
        "width": "weighted",
        "weight": 1,
        "vertical_align": "center",
        "elements": [
            {
                "tag": "markdown",
                "text_align": "center",
                "content": f"**{value}**\n{label}",
            }
        ],
    }


def _build_card_payload(*, title: str, elements: list[dict], template: str = "indigo") -> dict:
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title,
                },
                "template": template,
            },
            "elements": elements,
        },
    }


def _humanize_theme_name(theme: str) -> str:
    parts = []
    for chunk in str(theme).split("_"):
        upper_chunk = chunk.upper()
        if upper_chunk in {"AI", "RAG", "MCP", "LLM", "PR"}:
            parts.append(upper_chunk)
        elif chunk:
            parts.append(chunk.capitalize())
    return " ".join(parts)


def _render_focus_strip(metadata: dict | None = None) -> str | None:
    meta = metadata or {}
    themes = meta.get("top_themes") or []
    if not themes:
        return None
    readable = [_humanize_theme_name(str(theme)) for theme in themes if str(theme).strip()]
    if not readable:
        return None
    return f"**关注主题**  ·  {'  ·  '.join(readable[:3])}"


# ── Ecosystem Label ───────────────────────────────────────────────

_ECOSYSTEM_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (("claude-code", "claude code", "claudecode"), "Claude Code"),
    (("codex", "oh-my-codex"), "Codex"),
    (("mcp", "model context protocol", "mcp-server"), "MCP"),
    (("browser-use", "browser use", "browser", "playwright", "puppeteer"), "浏览器自动化"),
    (("rag", "graphrag", "retrieval"), "RAG"),
    (("agent", "agents", "agentic", "multi-agent"), "Agent"),
    (("workflow", "automation"), "工作流自动化"),
    (("prompt", "prompts", "cursor", "cursorrules"), "Prompt / Rules"),
    (("vllm", "llama.cpp", "inference", "ollama"), "模型推理"),
    (("dify",), "Dify 平台"),
    (("open-webui",), "Open WebUI"),
    (("copilot",), "Copilot / IDE"),
    (("skill", "skills", "superpowers"), "Skill 生态"),
    (("docker", "k8s", "kubernetes", "aks"), "云原生 / DevOps"),
    (("security", "auth", "compliance"), "安全"),
]


def _detect_ecosystem(item: dict) -> str:
    """从 item 的标题、描述、topics 中推断适配生态标签。"""
    parts = [
        item.get("title", ""),
        item.get("repo_full_name", ""),
        item.get("trait", ""),
        item.get("capability", ""),
        " ".join(item.get("topics", [])) if isinstance(item.get("topics"), list) else "",
        item.get("summary", ""),
    ]
    blob = " ".join(str(p) for p in parts if p).lower()
    for needles, label in _ECOSYSTEM_PATTERNS:
        if any(needle in blob for needle in needles):
            return label
    return "通用 AI 工具"


# ── Surge Section ────────────────────────────────────────────────

def _format_total_stars(stars: int) -> str:
    if stars >= 1000:
        return f"{stars / 1000:.1f}K★"
    if stars > 0:
        return f"{stars}★"
    return ""


def _render_surge_section(surge_items: list[dict]) -> str | None:
    """渲染高增速分区：紧凑单行，强调增长。"""
    if not surge_items:
        return None

    lines = [f"**Momentum Leaders · {len(surge_items)}**", ""]
    for i, item in enumerate(surge_items, 1):
        title = item.get("title", "")
        url = item.get("url", "")
        daily_delta = item.get("surge_daily_delta", 0)
        total_stars = item.get("stars", 0)
        stars_is_growth = item.get("stars_is_growth", False)

        link = f"[{title}]({url})" if url else title
        if stars_is_growth:
            # OSSInsight only: total stars unknown, only show delta
            line = f"**{i}.** {link}  +{daily_delta}★"
        else:
            total_str = _format_total_stars(total_stars)
            line = f"**{i}.** {link}  +{daily_delta}★  {total_str}"
        lines.append(line)

    lines.append("")
    lines.append("*来源：GitHub Trending / OSSInsight*")
    return "\n".join(lines)


# ── Item Rendering ────────────────────────────────────────────────

def _render_featured_item(item: dict, index: int, *, include_source_link: bool = True) -> str:
    """渲染精编条目：标题 + 看点 + 画像三行"""
    title = item.get("title", "")
    url = item.get("url", "")
    why_now = item.get("why_now", "")
    badge = _format_star_badge(item)
    kind = item.get("kind", "other")
    labels = PROFILE_LABELS.get(kind, PROFILE_LABELS["other"])

    # 行 1: 序号 + 可点击链接 + star 徽标
    badge_suffix = f"  {badge}" if badge else ""
    line1 = f"**{index}.** [{title}]({url}){badge_suffix}" if url else f"**{index}.** {title}{badge_suffix}"

    lines = [line1]
    if include_source_link:
        lines.append(_render_source_link(item, fallback_label="GitHub"))

    # 行 3: 看点（一句话）
    external_heat = _format_external_heat(item)
    if external_heat and why_now:
        lines.append(f"信号：{_truncate_text(f'{external_heat} · {why_now}', 80)}")
    elif external_heat:
        lines.append(f"信号：{_truncate_text(external_heat, 80)}")
    elif why_now:
        lines.append(f"信号：{_truncate_text(why_now, 80)}")

    # 行 3-5: 画像三段分行（有内容才输出）
    trait = item.get("trait", "")
    capability = item.get("capability", "")
    necessity = item.get("necessity", "")

    if trait:
        lines.append(f"▸ {labels['trait']}：{_truncate_text(trait, 50)}")
    if capability:
        lines.append(f"▸ {labels['capability']}：{_truncate_text(capability, 55)}")
    if necessity:
        lines.append(f"▸ {labels['necessity']}：{_truncate_text(necessity, 55)}")

    return "\n".join(lines)


def _render_compact_item(item: dict, index: int, *, include_source_link: bool = True) -> str:
    """渲染速览条目：单行 = 标题 + badge"""
    title = item.get("title", "")
    url = item.get("url", "")
    badge = _format_star_badge(item)
    badge_suffix = f"  {badge}" if badge else ""
    external_heat = _format_external_heat(item)
    detail_parts = []
    if include_source_link:
        detail_parts.append(_render_source_link(item, fallback_label="GitHub"))
    if external_heat:
        detail_parts.append(external_heat)
    detail_suffix = f"  ·  {'  ·  '.join(detail_parts)}" if detail_parts else ""
    if url:
        return f"**{index}.** [{title}]({url}){badge_suffix}{detail_suffix}"
    return f"**{index}.** {title}{badge_suffix}{detail_suffix}"


def _render_skill_item(item: dict, index: int, *, include_source_link: bool = True) -> str:
    """渲染技能条目：标题 + 生态标签 + trait"""
    title = item.get("title", "")
    url = item.get("url", "")
    badge = _format_star_badge(item)
    badge_suffix = f"  {badge}" if badge else ""
    line1 = f"**{index}.** [{title}]({url}){badge_suffix}" if url else f"**{index}.** {title}{badge_suffix}"

    lines = [line1]
    detail_parts = []
    if include_source_link:
        detail_parts.append(_render_source_link(item, fallback_label="GitHub"))
    detail_parts.append(f"适配栈：{_detect_ecosystem(item)}")
    lines.append("  ·  ".join(detail_parts))
    # 生态适配标签
    trait = item.get("trait", "")
    if trait:
        labels = PROFILE_LABELS.get(item.get("kind", "other"), PROFILE_LABELS["other"])
        lines.append(f"▸ {labels['trait']}：{_truncate_text(trait, 50)}")
    return "\n".join(lines)


# ── Section Rendering ─────────────────────────────────────────────

def _render_project_section(items: list[dict], *, featured_limit: int = FEATURED_LIMIT) -> str | None:
    """渲染项目分区：精编 + 速览两层"""
    if not items:
        return None

    section_title = _format_section_heading(
        SECTION_ICONS["project"],
        source_key=_shared_source_key(items),
    )
    lines = [section_title, ""]

    # 精编区
    featured = items[:featured_limit]
    for i, item in enumerate(featured, 1):
        lines.append(_render_featured_item(item, i, include_source_link=False))
        lines.append("")

    # 速览区
    compact = items[featured_limit:]
    if compact:
        lines.append("**延伸速览**")
        lines.append("")
        for i, item in enumerate(compact, featured_limit + 1):
            lines.append(_render_compact_item(item, i, include_source_link=False))

    return "\n".join(lines)


def _render_skill_section(items: list[dict]) -> str | None:
    """渲染技能分区：标题 + trait 精简模式"""
    if not items:
        return None

    section_title = _format_section_heading(
        SECTION_ICONS["skill"],
        source_key=_shared_source_key(items),
    )
    lines = [section_title, ""]
    for i, item in enumerate(items, 1):
        lines.append(_render_skill_item(item, i, include_source_link=False))
        lines.append("")
    return "\n".join(lines)


def _render_discussion_section(items: list[dict]) -> str | None:
    """渲染讨论分区：精编模式（discussion 通常量少、质高）"""
    if not items:
        return None

    section_title = _format_section_heading(
        SECTION_ICONS["discussion"],
        source_key=_shared_source_key(items),
    )
    lines = [section_title, ""]
    for i, item in enumerate(items, 1):
        lines.append(_render_featured_item(item, i, include_source_link=False))
        lines.append("")
    return "\n".join(lines)


def _render_tech_pulse_section(items: list[dict]) -> str | None:
    if not items:
        return None

    lines = []
    for index, item in enumerate(items, 1):
        title = item.get("title", "")
        url = item.get("url", "")
        source_label = item.get("source_label", item.get("source", "外部来源"))
        why_now = item.get("why_now", "") or item.get("summary", "")
        line = f"**{index}.** [{title}]({url})" if url else f"**{index}.** {title}"
        lines.append(line)
        detail_parts = [_render_source_link(item, fallback_label=source_label)]
        if why_now:
            detail_parts.append(f"信号：{_truncate_text(why_now, 72)}")
        lines.append("  ·  ".join(detail_parts))
        lines.append("")
    return "\n".join(lines)


def _render_builder_watch_section(sections: dict[str, list[dict]]) -> str | None:
    if not sections:
        return None

    lines = []
    for key in ("x", "podcast", "blog"):
        items = sections.get(key) or []
        if not items:
            continue
        lines.append(
            _format_section_heading(
                BUILDER_SECTION_LABELS.get(key, key.title()),
                count=len(items),
                source_key=_shared_source_key(items),
            )
        )
        for index, item in enumerate(items, 1):
            title = item.get("title", "")
            url = item.get("url", "")
            creator = item.get("creator", "")
            why_now = item.get("why_now", "") or item.get("summary", "")
            line = f"**{index}.** [{title}]({url})" if url else f"**{index}.** {title}"
            lines.append(line)
            detail_parts = []
            if creator and not _title_mentions_creator(title, creator):
                detail_parts.append(f"作者：{creator}")
            if why_now:
                detail_parts.append(f"信号：{_truncate_text(why_now, 72)}")
            if detail_parts:
                lines.append("  ·  ".join(detail_parts))
        lines.append("")
    return "\n".join(lines)


SECTION_RENDERERS = {
    "project": _render_project_section,
    "skill": _render_skill_section,
    "discussion": _render_discussion_section,
}


def _render_section(section_title: str, items: list[dict]) -> str | None:
    """通用分区渲染 — 仅作兜底，优先走 SECTION_RENDERERS"""
    if not items:
        return None
    lines = [section_title, ""]
    for i, item in enumerate(items, 1):
        lines.append(_render_featured_item(item, i))
        lines.append("")
    return "\n".join(lines)


# ── Overview Panel ────────────────────────────────────────────────

def _build_stats_panel(
    all_items: list[dict],
    metadata: dict,
    tech_items: list[dict] | None = None,
    builder_sections: dict[str, list[dict]] | None = None,
) -> dict:
    """构建 column_set 四列概览面板"""
    selected = len(all_items)
    tech_count = len(tech_items or [])
    builder_count = sum(len(items) for items in (builder_sections or {}).values())

    # 主题数
    theme_counts = metadata.get("theme_counts", {})
    top_themes = metadata.get("top_themes", [])
    theme_n = len(theme_counts) if theme_counts else len(top_themes)

    return {
        "tag": "column_set",
        "flex_mode": "bisect",
        "background_style": "grey",
        "horizontal_spacing": "default",
        "columns": [
            _build_metric_column(selected, "主榜"),
            _build_metric_column(tech_count, "热讯"),
            _build_metric_column(builder_count, "观察"),
            _build_metric_column(theme_n, "主题"),
        ],
    }


def _render_overview(items: list[dict]) -> str:
    """渲染概览统计（文字版 fallback）"""
    counts = Counter(
        "discussion" if item.get("kind", "other") in ("discussion", "issue", "pr") else item.get("kind", "other")
        for item in items
    )
    parts = []
    for kind, label in [("project", "项目"), ("skill", "技能"), ("discussion", "讨论")]:
        if counts.get(kind, 0):
            parts.append(f"**{counts[kind]}** {label}")
    return f"今日精选 **{len(items)}** 条：{'  ·  '.join(parts)}"


def _render_footer(today: date | None = None, metadata: dict | None = None) -> str:
    """渲染底部：日期 + 漏斗转化"""
    if not today:
        return ""
    meta = metadata or {}
    total = meta.get("count", 0)
    selected = meta.get("item_count", 0)
    if total and selected:
        return f"日期  ·  {today.isoformat()}  ·  来源  ·  GitHub / OSSInsight / Buzzing / Follow Builders  ·  {total} 候选 → {selected} 精选"
    return f"日期  ·  {today.isoformat()}  ·  来源  ·  GitHub / OSSInsight / Buzzing / Follow Builders"


def _section_order(*, project_first: bool) -> list[str]:
    if project_first:
        return ["project", "skill", "discussion"]
    return ["skill", "discussion", "project"]


def _item_identity(item: dict) -> str:
    for key in ("url", "candidate_id", "repo_full_name", "title"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return f"{key}:{value}"
    return repr(sorted(item.items()))


# ── Card Assembly ─────────────────────────────────────────────────

def build_digest_card(
    *,
    items: list[dict],
    secondary_items: list[dict] | None = None,
    tech_items: list[dict] | None = None,
    builder_sections: dict[str, list[dict]] | None = None,
    surge_items: list[dict] | None = None,
    metadata: dict | None = None,
    today: date | None = None,
    project_first: bool = True,
) -> dict:
    """构建飞书交互卡片 — 单版、四分区、分层密度"""
    metadata = metadata or {}
    date_str = today.isoformat() if today else ""
    surge_items = surge_items or []

    # 合并 items (兼容旧调用方传入 secondary_items 的情况)
    all_items = list(items)
    if secondary_items:
        seen = {_item_identity(item) for item in all_items}
        for item in secondary_items:
            key = _item_identity(item)
            if key not in seen:
                all_items.append(item)
                seen.add(key)

    # 爆款区的 repo 从核心项目区排除
    surge_repos = {item.get("repo_full_name") for item in surge_items if item.get("repo_full_name")}

    # 按 kind 分组
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in all_items:
        kind = item.get("kind", "other")
        if kind in ("issue", "pr"):
            kind = "discussion"
        # 已在爆款区展示的 repo 不再出现在核心项目区
        if kind == "project" and item.get("repo_full_name") in surge_repos:
            continue
        grouped[kind].append(item)

    elements: list[dict] = []

    elements.append({"tag": "markdown", "content": CARD_SUBTITLE, "text_size": "notation"})

    # ── 概览面板 ──
    if metadata.get("count"):
        elements.append(_build_stats_panel(all_items, metadata, tech_items=tech_items, builder_sections=builder_sections))
    else:
        # 无 metadata 时用文字概览
        elements.append({
            "tag": "markdown",
            "content": _render_overview(all_items),
        })
    focus_strip = _render_focus_strip(metadata)
    if focus_strip:
        elements.append({"tag": "markdown", "content": focus_strip})
    elements.append({"tag": "hr"})

    # ── 爆款监测（置顶） ──
    surge_content = _render_surge_section(surge_items)
    if surge_content is not None:
        elements.append({"tag": "markdown", "content": surge_content})
        elements.append({"tag": "hr"})

    # ── GitHub Radar ──
    github_copy = TRACK_COPY["github"]
    elements.append(
        _build_track_header(
            track_key="github",
            title=github_copy["title"],
            subtitle=github_copy["subtitle"],
            count=len(all_items),
            metric_label=github_copy["metric_label"],
        )
    )

    # ── GitHub 内部分区 ──
    for kind in _section_order(project_first=project_first):
        section_items = grouped.get(kind, [])
        renderer = SECTION_RENDERERS.get(kind)
        if renderer:
            content = renderer(section_items)
        else:
            title = SECTION_ICONS.get(kind, kind.title())
            content = _render_section(f"**{title}**", section_items)
        if content is not None:
            elements.append({"tag": "markdown", "content": content})

    tech_content = _render_tech_pulse_section(tech_items or [])
    builder_content = _render_builder_watch_section(builder_sections or {})
    if tech_content is not None:
        elements.append({"tag": "hr"})
        tech_copy = TRACK_COPY["tech"]
        elements.append(
            _build_track_header(
                track_key="tech",
                title=tech_copy["title"],
                subtitle=tech_copy["subtitle"],
                count=len(tech_items or []),
                metric_label=tech_copy["metric_label"],
            )
        )
        elements.append({"tag": "markdown", "content": tech_content})
        if builder_content is not None:
            elements.append({"tag": "hr"})

    if builder_content is not None:
        if tech_content is None:
            elements.append({"tag": "hr"})
        builder_copy = TRACK_COPY["builder"]
        elements.append(
            _build_track_header(
                track_key="builder",
                title=builder_copy["title"],
                subtitle=builder_copy["subtitle"],
                count=sum(len(items) for items in (builder_sections or {}).values()),
                metric_label=builder_copy["metric_label"],
            )
        )
        elements.append({"tag": "markdown", "content": builder_content})

    # ── Footer ──
    footer = _render_footer(today, metadata)
    if footer:
        elements.append({"tag": "markdown", "content": footer, "text_size": "notation"})

    return _build_card_payload(
        title=f"AI Builder Radar · {date_str}",
        elements=elements,
    )


def build_style_review_card(*, today: date | None = None) -> dict:
    """构建仅用于 review 的样式预览卡，不包含真实内容。"""
    date_str = today.isoformat() if today else ""
    elements: list[dict] = [
        {"tag": "markdown", "content": CARD_SUBTITLE, "text_size": "notation"},
        {
            "tag": "column_set",
            "flex_mode": "bisect",
            "background_style": "grey",
            "horizontal_spacing": "default",
            "columns": [
                _build_metric_column("—", "主榜"),
                _build_metric_column("—", "热讯"),
                _build_metric_column("—", "观察"),
                _build_metric_column("—", "主题"),
            ],
        },
        {
            "tag": "markdown",
            "content": f"**样式预览**  ·  {STYLE_REVIEW_NOTE}",
        },
        {"tag": "hr"},
    ]

    github_copy = TRACK_COPY["github"]
    elements.append(
        _build_track_header(
            track_key="github",
            title=github_copy["title"],
            subtitle=github_copy["subtitle"],
            count=0,
            metric_label=github_copy["metric_label"],
        )
    )
    elements.append(
        {
            "tag": "markdown",
            "content": (
                "**核心项目**  ·  <link icon='platform_outlined' url='https://github.com'>GitHub</link>\n"
                "样式占位：检查标题、数字面板与主区留白。\n\n"
                "**技能与 MCP**  ·  <link icon='platform_outlined' url='https://github.com'>GitHub</link>\n"
                "样式占位：检查次级栏目密度与信息层级。\n\n"
                "**讨论与提案**  ·  <link icon='platform_outlined' url='https://github.com'>GitHub</link>\n"
                "样式占位：检查正文节奏与分区间距。"
            ),
        }
    )
    elements.append({"tag": "hr"})

    tech_copy = TRACK_COPY["tech"]
    elements.append(
        _build_track_header(
            track_key="tech",
            title=tech_copy["title"],
            subtitle=tech_copy["subtitle"],
            count=0,
            metric_label=tech_copy["metric_label"],
        )
    )
    elements.append(
        {
            "tag": "markdown",
            "content": "**样式预览 · 科技热讯**\n样式占位：检查副栏目是否足够轻，不抢 GitHub 主区。",
        }
    )
    elements.append({"tag": "hr"})

    builder_copy = TRACK_COPY["builder"]
    elements.append(
        _build_track_header(
            track_key="builder",
            title=builder_copy["title"],
            subtitle=builder_copy["subtitle"],
            count=0,
            metric_label=builder_copy["metric_label"],
        )
    )
    elements.append(
        {
            "tag": "markdown",
            "content": (
                "**X**  ·  <link icon='internet_outlined' url='https://x.com'>X</link>\n"
                "样式占位：检查人物流的标题节奏。\n\n"
                "**Podcast**  ·  <link icon='file-link-video_outlined' url='https://www.youtube.com'>YouTube</link>\n"
                "样式占位：检查媒体型条目的密度。\n\n"
                "**Blog**\n样式占位：检查收尾区的视觉重量。"
            ),
        }
    )
    elements.append(
        {
            "tag": "markdown",
            "content": f"日期  ·  {date_str}  ·  模式  ·  样式预览",
            "text_size": "notation",
        }
    )

    return _build_card_payload(
        title=f"AI Builder Radar · {date_str}",
        elements=elements,
    )


def build_alert_cards(*, title: str, message: str, metadata: dict | None = None) -> list[dict]:
    """构建告警卡片"""
    elements = [{"tag": "markdown", "content": f"⚠️ {message}"}]
    return [
        _build_card_payload(title=title, elements=elements, template="red")
    ]


def send_cards(*, webhook_url: str, cards: list[dict]) -> None:
    """发送卡片到飞书 webhook"""
    with httpx.Client(timeout=15.0) as client:
        for payload in cards:
            response = client.post(webhook_url, json=payload)
            response.raise_for_status()
            response_data = response.json()
            if not isinstance(response_data, dict):
                continue

            code = response_data.get("code")
            status_code = response_data.get("StatusCode")
            is_success = (code in (None, 0)) and (status_code in (None, 0))
            if is_success:
                continue

            message = (
                response_data.get("msg")
                or response_data.get("StatusMessage")
                or response_data.get("message")
                or "unknown error"
            )
            raise RuntimeError(
                f"Feishu webhook rejected message: code={code!r} status_code={status_code!r} msg={message}"
            )
