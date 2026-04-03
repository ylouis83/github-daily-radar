"""Feishu interactive card rendering and delivery.

Design principles (v2):
  • 单版输出 — 不再分 A/B，一张卡片展示所有精选
  • 三大分区 — 🚀 核心 AI 项目 / 🧩 MCP & Skills / 💬 提案与讨论
  • 分层密度 — 精编条目 (前 N 条) 带完整画像；其余紧凑速览
  • column_set 概览面板 — 三列数字冲击
  • 空分区不渲染
"""
from __future__ import annotations

from datetime import date
from collections import Counter, defaultdict

import httpx

# ── Constants ──────────────────────────────────────────────────────
# 项目区默认全部展示完整画像，避免第 6 条开始被压成单行
FEATURED_LIMIT = 20

_VELOCITY_EMOJI = {
    "explosion": "💥",
    "surge": "🔥",
    "rising": "📈",
    "new": "🆕",
}

SECTION_ICONS = {
    "project": "🚀 核心 AI 项目",
    "skill": "🧩 MCP & Skills",
    "discussion": "💬 提案与讨论",
}

# kind → 画像结构化字段标签
PROFILE_LABELS = {
    "project":    {"trait": "特点", "capability": "核心能力", "necessity": "引入必要性"},
    "skill":      {"trait": "特点", "capability": "核心能力", "necessity": "纳入必要性"},
    "discussion": {"trait": "焦点", "capability": "核心观点", "necessity": "跟进必要性"},
    "other":      {"trait": "特点", "capability": "核心能力", "necessity": "引入必要性"},
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
    """格式化 star 徽标：🔥+1161⭐ 或 ⭐12.3K"""
    delta = item.get("star_delta_1d", 0)
    velocity = item.get("star_velocity", "")
    emoji = _VELOCITY_EMOJI.get(velocity, "")

    if delta and delta > 50:
        return f"{emoji}+{delta}⭐"

    stars = item.get("stars", 0)
    if stars >= 1000:
        return f"⭐{stars / 1000:.1f}K"
    elif stars > 0:
        return f"⭐{stars}"
    return ""


def _format_star_tag(item: dict) -> str:
    """用 text_tag 彩色标签展示 star 增量（仅精编条目）"""
    delta = item.get("star_delta_1d", 0)
    velocity = item.get("star_velocity", "")
    color = _VELOCITY_TAG_COLOR.get(velocity, "neutral")

    if delta and delta > 50:
        emoji = _VELOCITY_EMOJI.get(velocity, "")
        return f"<text_tag color='{color}'>{emoji}+{delta}⭐</text_tag>"

    stars = item.get("stars", 0)
    if stars >= 1000:
        return f"<text_tag color='neutral'>⭐{stars / 1000:.1f}K</text_tag>"
    elif stars > 0:
        return f"<text_tag color='neutral'>⭐{stars}</text_tag>"
    return ""


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

    # 行 2: 看点（一句话）
    if why_now:
        lines.append(f"📌 {_truncate_text(why_now, 80)}")

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
    if url:
        return f"**{index}.** [{title}]({url}){badge_suffix}"
    return f"**{index}.** {title}{badge_suffix}"


def _render_skill_item(item: dict, index: int) -> str:
    """渲染技能条目：标题 + 仅保留 trait 一行"""
    title = item.get("title", "")
    url = item.get("url", "")
    badge = _format_star_badge(item)
    badge_suffix = f"  {badge}" if badge else ""
    line1 = f"**{index}.** [{title}]({url}){badge_suffix}" if url else f"**{index}.** {title}{badge_suffix}"

    lines = [line1]
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

    section_title = f"**{SECTION_ICONS['project']}**"
    lines = [section_title, ""]

    # 精编区
    featured = items[:featured_limit]
    for i, item in enumerate(featured, 1):
        lines.append(_render_featured_item(item, i))
        lines.append("")

    # 速览区
    compact = items[featured_limit:]
    if compact:
        for i, item in enumerate(compact, featured_limit + 1):
            lines.append(_render_compact_item(item, i))

    return "\n".join(lines)


def _render_skill_section(items: list[dict]) -> str | None:
    """渲染技能分区：标题 + trait 精简模式"""
    if not items:
        return None

    section_title = f"**{SECTION_ICONS['skill']}**"
    lines = [section_title, ""]
    for i, item in enumerate(items, 1):
        lines.append(_render_skill_item(item, i))
        lines.append("")
    return "\n".join(lines)


def _render_discussion_section(items: list[dict]) -> str | None:
    """渲染讨论分区：精编模式（discussion 通常量少、质高）"""
    if not items:
        return None

    section_title = f"**{SECTION_ICONS['discussion']}**"
    lines = [section_title, ""]
    for i, item in enumerate(items, 1):
        lines.append(_render_featured_item(item, i))
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
) -> dict:
    """构建 column_set 三列概览面板"""
    total_count = metadata.get("count", len(all_items))
    selected = len(all_items)

    # 主题数
    theme_counts = metadata.get("theme_counts", {})
    theme_n = len(theme_counts) if theme_counts else 0

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
        return f"📅 {today.isoformat()}  ·  {total} 候选 → {selected} 精选"
    return f"📅 {today.isoformat()}"


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
    metadata: dict | None = None,
    today: date | None = None,
    project_first: bool = True,
) -> dict:
    """构建飞书交互卡片 — 单版、三分区、分层密度"""
    metadata = metadata or {}
    date_str = today.isoformat() if today else ""

    # 合并 items (兼容旧调用方传入 secondary_items 的情况)
    all_items = list(items)
    if secondary_items:
        seen = {_item_identity(item) for item in all_items}
        for item in secondary_items:
            key = _item_identity(item)
            if key not in seen:
                all_items.append(item)
                seen.add(key)

    # 按 kind 分组
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in all_items:
        kind = item.get("kind", "other")
        if kind in ("issue", "pr"):
            kind = "discussion"
        grouped[kind].append(item)

    elements: list[dict] = []

    # ── 概览面板 ──
    if metadata.get("count"):
        elements.append(_build_stats_panel(all_items, metadata))
    else:
        # 无 metadata 时用文字概览
        elements.append({
            "tag": "markdown",
            "content": _render_overview(all_items),
        })
    elements.append({"tag": "hr"})

    # ── 三大分区 ──
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
                    "content": f"🔭 GitHub 每日雷达 · {date_str}",
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
