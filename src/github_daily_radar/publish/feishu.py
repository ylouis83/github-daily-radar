"""Feishu interactive card rendering and delivery."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

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
    title = item.get("title", "")
    url = item.get("url", "")
    summary = item.get("summary", "")
    badge = _format_star_badge(item)

    # 第 1 行: 序号 + 可点击链接
    line1 = f"**{index}.** [{title}]({url})" if url else f"**{index}.** {title}"

    # 第 2 行: 星标 + 摘要 (按单词截断)
    parts = []
    if badge:
        parts.append(badge)
    if summary:
        # 按单词边界截断
        s = summary[:100]
        if len(summary) > 100 and " " in s:
            s = s.rsplit(" ", 1)[0] + "…"
        parts.append(s)
    line2 = f"      {' · '.join(parts)}" if parts else ""

    return f"{line1}\n{line2}" if line2 else line1


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


def _render_footer(metadata: dict, today: date | None = None) -> str:
    """渲染底部运维数据 1 行"""
    parts = []
    count = metadata.get("count", 0)
    a_count = metadata.get("a_count", 0)
    if count:
        parts.append(f"📊 {count}候选→{a_count}精选")
    api = metadata.get("api_usage", {})
    if api:
        search = api.get("search_used", 0)
        gql = api.get("graphql_used", 0)
        parts.append(f"🔍{search}搜索 + {gql}GraphQL")
    editorial = metadata.get("editorial", 0)
    if editorial:
        parts.append(f"✍️{editorial}条LLM精编")
    if today:
        parts.append(f"🕐{today.isoformat()}")
    return " · ".join(parts)


def build_digest_card(
    *,
    items: list[dict],
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

    # 概览
    elements.append({
        "tag": "markdown",
        "content": _render_overview(items),
    })
    elements.append({"tag": "hr"})

    # 各分区 — 空分区不渲染
    for kind in ["project", "skill", "discussion"]:
        section_items = grouped.get(kind, [])
        title = SECTION_ICONS.get(kind, kind.title())
        content = _render_section(f"**{title}**", section_items)
        if content is not None:
            elements.append({"tag": "markdown", "content": content})
            elements.append({"tag": "hr"})

    # 底部运维信息
    elements.append({
        "tag": "markdown",
        "content": _render_footer(metadata, today),
    })

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
    if metadata:
        elements.append({"tag": "markdown", "content": f"`{metadata}`"})
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
