"""Feishu interactive card rendering and delivery.

Design principles (v3):
  • 单版输出 — 不再分 A/B，一张卡片展示所有精选
  • 四大分区 — 💥 今日爆款 / 🚀 核心 AI 项目 / 🧩 MCP & Skills / 💬 提案与讨论
  • 爆款区 — 仅含 TrendingCollector + OSSInsight 日增 ≥200⭐ 的项目，与核心项目互斥
  • 分层密度 — 精编条目 (前 N 条) 带完整画像；其余紧凑速览
  • column_set 概览面板 — 三列数字冲击
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
    "project": "Core Projects",
    "skill": "Skills & MCP",
    "discussion": "Discussion Signals",
}

BUILDER_SECTION_LABELS = {
    "x": "X",
    "podcast": "Video / Podcast",
    "blog": "Blog",
}

TRACK_COPY = {
    "github": {
        "title": "GitHub Radar",
        "subtitle": "开源仓库、技能资产与讨论议题",
        "metric_label": "主榜条目",
    },
    "tech": {
        "title": "Tech Pulse",
        "subtitle": "产品发布、工程信号与外部科技动态",
        "metric_label": "外部热讯",
    },
    "builder": {
        "title": "Builder Signals",
        "subtitle": "创作者观点、视频与长文线索",
        "metric_label": "Builder Picks",
    },
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


def _render_source_line(item: dict, *, fallback_label: str | None = None) -> str:
    label, icon_token, url = _resolve_source_meta(item, fallback_label=fallback_label)
    if url:
        return f"来源：{_format_source_link(label=label, url=url, icon_token=icon_token)}"
    return f"来源：{label}"


def _build_track_header(*, title: str, subtitle: str, count: int, metric_label: str) -> dict:
    return {
        "tag": "column_set",
        "flex_mode": "bisect",
        "horizontal_spacing": "default",
        "columns": [
            {
                "tag": "column",
                "width": "weighted",
                "weight": 3,
                "vertical_align": "center",
                "elements": [
                    {
                        "tag": "markdown",
                        "content": f"**{title}**\n{subtitle}",
                    }
                ],
            },
            {
                "tag": "column",
                "width": "weighted",
                "weight": 1,
                "vertical_align": "center",
                "elements": [
                    {
                        "tag": "markdown",
                        "text_align": "right",
                        "content": f"**{count}**\n{metric_label}",
                    }
                ],
            },
        ],
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
    return f"**Focus Areas**  ·  {'  ·  '.join(readable[:3])}"


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

    lines = ["**Momentum Leaders**", ""]
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

def _render_featured_item(item: dict, index: int) -> str:
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
    lines.append(_render_source_line(item, fallback_label="GitHub"))

    # 行 3: 看点（一句话）
    external_heat = _format_external_heat(item)
    if external_heat and why_now:
        lines.append(f"观察：{_truncate_text(f'{external_heat} · {why_now}', 80)}")
    elif external_heat:
        lines.append(f"观察：{_truncate_text(external_heat, 80)}")
    elif why_now:
        lines.append(f"观察：{_truncate_text(why_now, 80)}")

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


def _render_compact_item(item: dict, index: int) -> str:
    """渲染速览条目：单行 = 标题 + badge"""
    title = item.get("title", "")
    url = item.get("url", "")
    badge = _format_star_badge(item)
    badge_suffix = f"  {badge}" if badge else ""
    source_line = _render_source_line(item, fallback_label="GitHub")
    external_heat = _format_external_heat(item)
    heat_suffix = f"  ·  {external_heat}" if external_heat else ""
    if url:
        return f"**{index}.** [{title}]({url}){badge_suffix}  ·  {source_line}{heat_suffix}"
    return f"**{index}.** {title}{badge_suffix}  ·  {source_line}{heat_suffix}"


def _render_skill_item(item: dict, index: int) -> str:
    """渲染技能条目：标题 + 生态标签 + trait"""
    title = item.get("title", "")
    url = item.get("url", "")
    badge = _format_star_badge(item)
    badge_suffix = f"  {badge}" if badge else ""
    line1 = f"**{index}.** [{title}]({url}){badge_suffix}" if url else f"**{index}.** {title}{badge_suffix}"

    lines = [line1]
    lines.append(_render_source_line(item, fallback_label="GitHub"))
    # 生态适配标签
    ecosystem = _detect_ecosystem(item)
    lines.append(f"适配：{ecosystem}")
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

    section_title = f"**{SECTION_ICONS['project']} · {len(items)}**"
    lines = [section_title, ""]

    # 精编区
    featured = items[:featured_limit]
    for i, item in enumerate(featured, 1):
        lines.append(_render_featured_item(item, i))
        lines.append("")

    # 速览区
    compact = items[featured_limit:]
    if compact:
        lines.append("**Quick Scan**")
        lines.append("")
        for i, item in enumerate(compact, featured_limit + 1):
            lines.append(_render_compact_item(item, i))

    return "\n".join(lines)


def _render_skill_section(items: list[dict]) -> str | None:
    """渲染技能分区：标题 + trait 精简模式"""
    if not items:
        return None

    section_title = f"**{SECTION_ICONS['skill']} · {len(items)}**"
    lines = [section_title, ""]
    for i, item in enumerate(items, 1):
        lines.append(_render_skill_item(item, i))
        lines.append("")
    return "\n".join(lines)


def _render_discussion_section(items: list[dict]) -> str | None:
    """渲染讨论分区：精编模式（discussion 通常量少、质高）"""
    if not items:
        return None

    section_title = f"**{SECTION_ICONS['discussion']} · {len(items)}**"
    lines = [section_title, ""]
    for i, item in enumerate(items, 1):
        lines.append(_render_featured_item(item, i))
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
        detail_parts = [_render_source_line(item, fallback_label=source_label)]
        if why_now:
            detail_parts.append(f"观察：{_truncate_text(why_now, 72)}")
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
        lines.append(f"**{BUILDER_SECTION_LABELS.get(key, key.title())}**")
        for index, item in enumerate(items, 1):
            title = item.get("title", "")
            url = item.get("url", "")
            creator = item.get("creator", "")
            why_now = item.get("why_now", "") or item.get("summary", "")
            line = f"**{index}.** [{title}]({url})" if url else f"**{index}.** {title}"
            lines.append(line)
            detail_parts = []
            detail_parts.append(_render_source_line(item, fallback_label=creator or key.title()))
            if creator:
                detail_parts.append(f"作者：{creator}")
            if why_now:
                detail_parts.append(f"观察：{_truncate_text(why_now, 72)}")
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
    """构建 column_set 三列概览面板"""
    total_count = metadata.get("count", len(all_items))
    selected = len(all_items)
    tech_count = len(tech_items or [])
    builder_count = sum(len(items) for items in (builder_sections or {}).values())

    # 主题数
    theme_counts = metadata.get("theme_counts", {})
    theme_n = len(theme_counts) if theme_counts else 0

    if not tech_count and not builder_count:
        return {
            "tag": "column_set",
            "flex_mode": "bisect",
            "background_style": "grey",
            "horizontal_spacing": "default",
            "columns": [
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 1,
                    "vertical_align": "center",
                    "elements": [
                        {
                            "tag": "markdown",
                            "text_align": "center",
                            "content": f"**{total_count}**\n候选仓库",
                        }
                    ],
                },
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 1,
                    "vertical_align": "center",
                    "elements": [
                        {
                            "tag": "markdown",
                            "text_align": "center",
                            "content": f"**{selected}**\n今日精选",
                        }
                    ],
                },
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 1,
                    "vertical_align": "center",
                    "elements": [
                        {
                            "tag": "markdown",
                            "text_align": "center",
                            "content": f"**{theme_n}**\n覆盖主题",
                        }
                    ],
                },
            ],
        }

    return {
        "tag": "column_set",
        "flex_mode": "bisect",
        "background_style": "grey",
        "horizontal_spacing": "default",
        "columns": [
            {
                "tag": "column",
                "width": "weighted",
                "weight": 1,
                "vertical_align": "center",
                "elements": [
                    {
                        "tag": "markdown",
                        "text_align": "center",
                        "content": f"**{selected}**\nGitHub",
                    }
                ],
            },
            {
                "tag": "column",
                "width": "weighted",
                "weight": 1,
                "vertical_align": "center",
                "elements": [
                    {
                        "tag": "markdown",
                        "text_align": "center",
                        "content": f"**{tech_count}**\nTech Pulse",
                    }
                ],
            },
            {
                "tag": "column",
                "width": "weighted",
                "weight": 1,
                "vertical_align": "center",
                "elements": [
                    {
                        "tag": "markdown",
                        "text_align": "center",
                        "content": f"**{builder_count}**\nBuilders",
                    }
                ],
            },
            {
                "tag": "column",
                "width": "weighted",
                "weight": 1,
                "vertical_align": "center",
                "elements": [
                    {
                        "tag": "markdown",
                        "text_align": "center",
                        "content": f"**{total_count}**\n候选池",
                    }
                ],
            },
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
        return f"Date  ·  {today.isoformat()}  ·  Sources  ·  GitHub / OSSInsight / Buzzing / Follow Builders  ·  {total} 候选 → {selected} 精选"
    return f"Date  ·  {today.isoformat()}  ·  Sources  ·  GitHub / OSSInsight / Buzzing / Follow Builders"


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
            elements.append({"tag": "hr"})

    tech_content = _render_tech_pulse_section(tech_items or [])
    if tech_content is not None:
        tech_copy = TRACK_COPY["tech"]
        elements.append(
            _build_track_header(
                title=tech_copy["title"],
                subtitle=tech_copy["subtitle"],
                count=len(tech_items or []),
                metric_label=tech_copy["metric_label"],
            )
        )
        elements.append({"tag": "markdown", "content": tech_content})
        elements.append({"tag": "hr"})

    builder_content = _render_builder_watch_section(builder_sections or {})
    if builder_content is not None:
        builder_copy = TRACK_COPY["builder"]
        elements.append(
            _build_track_header(
                title=builder_copy["title"],
                subtitle=builder_copy["subtitle"],
                count=sum(len(items) for items in (builder_sections or {}).values()),
                metric_label=builder_copy["metric_label"],
            )
        )
        elements.append({"tag": "markdown", "content": builder_content})
        elements.append({"tag": "hr"})

    # ── Footer ──
    footer = _render_footer(today, metadata)
    if footer:
        elements.append({"tag": "markdown", "content": footer, "text_size": "notation"})

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"AI Builder Radar · {date_str}",
                },
                "template": "indigo",
            },
            "elements": elements,
        },
    }


def build_alert_cards(*, title: str, message: str, metadata: dict | None = None) -> list[dict]:
    """构建告警卡片"""
    elements = [{"tag": "markdown", "content": f"⚠️ {message}"}]
    return [
        {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "red",
                },
                "elements": elements,
            },
        }
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
