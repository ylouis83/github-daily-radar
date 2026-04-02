"""Feishu interactive card rendering and delivery.

Design principles:
  • 高密度 + 低噪音 — 每一行都在输出可操作信号
  • 三行结构 — 标题 → 看点一句话 → 画像三段
  • 画像分行 — 特点 / 核心能力 / 必要性 各一行，不做一行塞死
  • 空分区不渲染 — 不出现"今日暂无"
"""
from __future__ import annotations

from datetime import date
from collections import Counter, defaultdict

import httpx

# ── Emoji constants ──────────────────────────────────────────────
_VELOCITY_EMOJI = {
    "explosion": "💥",
    "surge": "🔥",
    "rising": "📈",
    "new": "🆕",
}

SECTION_ICONS = {
    "project": "🚀 必看项目",
    "skill": "🧩 发现技能",
    "discussion": "💬 提案与讨论",
}

SECTION_ICONS_B = {
    "project": "📦 更多项目",
    "skill": "🔧 更多技能",
    "discussion": "🗣️ 更多讨论",
}

# kind → 画像结构化字段标签
PROFILE_LABELS = {
    "project":    {"trait": "特点", "capability": "核心能力", "necessity": "引入必要性"},
    "skill":      {"trait": "特点", "capability": "核心能力", "necessity": "纳入必要性"},
    "discussion": {"trait": "焦点", "capability": "核心观点", "necessity": "跟进必要性"},
    "other":      {"trait": "特点", "capability": "核心能力", "necessity": "引入必要性"},
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
    if stars >= 10000:
        return f"⭐{stars / 1000:.1f}K"
    elif stars >= 1000:
        return f"⭐{stars / 1000:.1f}K"
    elif stars > 0:
        return f"⭐{stars}"
    return ""


# ── Item Rendering ────────────────────────────────────────────────

def _render_item_a(item: dict, index: int) -> str:
    """渲染 A 版条目：标题 + 看点 + 画像三行"""
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


def _render_item_b(item: dict, index: int) -> str:
    """渲染 B 版条目：紧凑两行"""
    title = item.get("title", "")
    url = item.get("url", "")
    why_now = item.get("why_now", "")
    badge = _format_star_badge(item)

    badge_suffix = f"  {badge}" if badge else ""
    line1 = f"**{index}.** [{title}]({url}){badge_suffix}" if url else f"**{index}.** {title}{badge_suffix}"

    lines = [line1]
    if why_now:
        lines.append(f"      {_truncate_text(why_now, 72)}")
    return "\n".join(lines)


# ── Section Rendering ─────────────────────────────────────────────

def _render_section(section_title: str, items: list[dict], *, compact: bool = False) -> str | None:
    """渲染一个完整分区，空分区返回 None"""
    if not items:
        return None

    renderer = _render_item_b if compact else _render_item_a
    lines = [section_title, ""]
    for i, item in enumerate(items, 1):
        lines.append(renderer(item, i))
        lines.append("")
    return "\n".join(lines)


def _render_overview(items: list[dict]) -> str:
    """渲染概览统计"""
    counts = Counter(
        "discussion" if item.get("kind", "other") in ("discussion", "issue", "pr") else item.get("kind", "other")
        for item in items
    )
    parts = []
    for kind, label in [("project", "项目"), ("skill", "技能"), ("discussion", "讨论")]:
        if counts.get(kind, 0):
            parts.append(f"**{counts[kind]}** {label}")
    return f"精选 **{len(items)}** 条：{'  ·  '.join(parts)}"


def _render_footer(today: date | None = None, metadata: dict | None = None) -> str:
    """渲染底部：时间戳 + 运行指标"""
    parts = []
    if today:
        parts.append(f"📅 {today.isoformat()}")
    if metadata:
        api_usage = metadata.get("api_usage") or {}
        search_used = api_usage.get("search_used")
        graphql_used = api_usage.get("graphql_used")
        count = metadata.get("count", 0)
        editorial = metadata.get("editorial", 0)
        metrics_parts = []
        if count:
            metrics_parts.append(f"候选 {count}")
        if editorial:
            metrics_parts.append(f"LLM 精编 {editorial}")
        if search_used is not None:
            metrics_parts.append(f"Search {search_used}")
        if graphql_used is not None:
            metrics_parts.append(f"GraphQL {graphql_used}")
        if metrics_parts:
            parts.append(" · ".join(metrics_parts))
    return "  |  ".join(parts) if parts else ""


# ── Card Assembly ─────────────────────────────────────────────────

def build_digest_card(
    *,
    items: list[dict],
    secondary_items: list[dict] | None = None,
    metadata: dict | None = None,
    today: date | None = None,
) -> dict:
    """构建飞书交互卡片 — 高密度、低噪音、结构化"""
    metadata = metadata or {}
    date_str = today.isoformat() if today else ""

    # ── A 版分组 ──
    a_grouped: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        kind = item.get("kind", "other")
        if kind in ("issue", "pr"):
            kind = "discussion"
        a_grouped[kind].append(item)

    elements: list[dict] = []

    # ── A 概览 ──
    elements.append({
        "tag": "markdown",
        "content": f"**🅰️ 精编版**\n{_render_overview(items)}",
    })
    elements.append({"tag": "hr"})

    # ── A 各分区 ──
    for kind in ["project", "skill", "discussion"]:
        section_items = a_grouped.get(kind, [])
        title = SECTION_ICONS.get(kind, kind.title())
        content = _render_section(f"**{title}**", section_items, compact=False)
        if content is not None:
            elements.append({"tag": "markdown", "content": content})
            elements.append({"tag": "hr"})

    # ── B 版 ──
    if secondary_items:
        b_grouped: dict[str, list[dict]] = defaultdict(list)
        for item in secondary_items:
            kind = item.get("kind", "other")
            if kind in ("issue", "pr"):
                kind = "discussion"
            b_grouped[kind].append(item)

        elements.append({
            "tag": "markdown",
            "content": f"**🅱️ 扫一眼**\n{_render_overview(secondary_items)}",
        })
        elements.append({"tag": "hr"})

        for kind in ["project", "skill", "discussion"]:
            section_items = b_grouped.get(kind, [])
            title = SECTION_ICONS_B.get(kind, kind.title())
            content = _render_section(f"**{title}**", section_items, compact=True)
            if content is not None:
                elements.append({"tag": "markdown", "content": content})
                elements.append({"tag": "hr"})

    # ── Footer ──
    footer = _render_footer(today, metadata)
    if footer:
        elements.append({"tag": "markdown", "content": footer})

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🔭 GitHub 每日雷达 · {date_str}",
                },
                "template": "blue",
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
