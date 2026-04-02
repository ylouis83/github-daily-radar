"""Feishu interactive card rendering and delivery."""
from __future__ import annotations

from datetime import date
from collections import Counter, defaultdict

import httpx

# Star 变化的 emoji 映射
_VELOCITY_EMOJI = {
    "explosion": "💥",
    "surge": "🔥",
    "rising": "📈",
    "new": "🆕",
}

# Section emoji 映射
SECTION_ICONS = {
    "project": "🚀 热门项目",
    "skill": "🧩 发现技能",
    "discussion": "💬 提案与讨论",
}

ITEM_COPY_LABELS = {
    "project": {"signal": "看点", "summary": "项目摘要"},
    "skill": {"signal": "可复用", "summary": "技能摘要"},
    "discussion": {"signal": "讨论焦点", "summary": "方案摘要"},
    "other": {"signal": "信号", "summary": "摘要"},
}


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
    """格式化 star 徽标：🔥+1161⭐ 或 ⭐131K"""
    delta = item.get("star_delta_1d", 0)
    velocity = item.get("star_velocity", "")
    emoji = _VELOCITY_EMOJI.get(velocity, "")

    if delta and delta > 50:
        return f"{emoji}+{delta}⭐"

    stars = item.get("stars", 0)
    if stars >= 1000:
        return f"⭐{stars // 1000}K"
    elif stars > 0:
        return f"⭐{stars}"
    return ""


def _render_item(item: dict, index: int) -> str:
    """渲染单个条目为紧凑 markdown"""
    kind = item.get("kind", "other")
    labels = ITEM_COPY_LABELS.get(kind, ITEM_COPY_LABELS["other"])
    title = item.get("title", "")
    url = item.get("url", "")
    summary = item.get("summary", "")
    why_now = item.get("why_now", "")
    badge = _format_star_badge(item)

    # 第 1 行: 序号 + 可点击链接
    line1 = f"**{index}.** [{title}]({url})" if url else f"**{index}.** {title}"

    # 第 2 行: 星标 + 当前看点
    parts = []
    if badge:
        parts.append(badge)
    if why_now:
        parts.append(f"{labels['signal']}：{_truncate_text(why_now, 72)}")
    line2 = f"      {' · '.join(parts)}" if parts else ""

    # 第 3 行: 中文摘要
    line3 = f"      {labels['summary']}：{_truncate_text(summary, 100)}" if summary else ""

    lines = [line1]
    if line2:
        lines.append(line2)
    if line3:
        lines.append(line3)
    return "\n".join(lines)


def _render_section(section_title: str, items: list[dict]) -> str | None:
    """渲染一个完整分区，空分区返回 None"""
    if not items:
        return None

    lines = [section_title, ""]
    for i, item in enumerate(items, 1):
        lines.append(_render_item(item, i))
        lines.append("")
    return "\n".join(lines)


def _render_overview(items: list[dict]) -> str:
    """渲染 1 行概览"""
    counts = Counter(
        "discussion" if item.get("kind", "other") in ("discussion", "issue", "pr") else item.get("kind", "other")
        for item in items
    )

    parts = []
    if counts.get("project", 0):
        parts.append(f"{counts['project']} 项目")
    if counts.get("skill", 0):
        parts.append(f"{counts['skill']} 技能")
    if counts.get("discussion", 0):
        parts.append(f"{counts['discussion']} 讨论")

    return f"今日精选 {len(items)} 条：{'  ·  '.join(parts)}"


def _render_footer(today: date | None = None) -> str:
    """仅渲染时间戳，避免把运行信息放进卡片。"""
    if not today:
        return ""
    return f"🕐{today.isoformat()}"


def build_digest_card(
    *,
    items: list[dict],
    secondary_items: list[dict] | None = None,
    metadata: dict | None = None,
    today: date | None = None,
) -> dict:
    """构建单张精美飞书卡片"""
    metadata = metadata or {}
    date_str = today.isoformat() if today else ""

    # 按 kind 分组
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        kind = item.get("kind", "other")
        if kind in ("issue", "pr"):
            kind = "discussion"
        grouped[kind].append(item)

    # 构建 elements
    elements: list[dict] = []

    # A 概览
    elements.append(
        {
            "tag": "markdown",
            "content": "**A 精编版 · 今日概览**\n" + _render_overview(items),
        }
    )
    elements.append({"tag": "hr"})

    # A 各分区 — 空分区不渲染
    for kind in ["project", "skill", "discussion"]:
        section_items = grouped.get(kind, [])
        title = SECTION_ICONS.get(kind, kind.title())
        content = _render_section(f"**{title}**", section_items)
        if content is not None:
            elements.append({"tag": "markdown", "content": content})
            elements.append({"tag": "hr"})

    # B 版作为同一卡片的补充区
    if secondary_items:
        secondary_grouped: dict[str, list[dict]] = defaultdict(list)
        for item in secondary_items:
            kind = item.get("kind", "other")
            if kind in ("issue", "pr"):
                kind = "discussion"
            secondary_grouped[kind].append(item)

        elements.append(
            {
                "tag": "markdown",
                "content": "**B 保留版 · 更多值得扫一眼**\n" + _render_overview(secondary_items),
            }
        )
        elements.append({"tag": "hr"})

        for kind in ["project", "skill", "discussion"]:
            section_items = secondary_grouped.get(kind, [])
            title = SECTION_ICONS.get(kind, kind.title())
            content = _render_section(f"**{title}**", section_items)
            if content is not None:
                elements.append({"tag": "markdown", "content": content})
                elements.append({"tag": "hr"})

    # 底部时间戳
    footer = _render_footer(today)
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
