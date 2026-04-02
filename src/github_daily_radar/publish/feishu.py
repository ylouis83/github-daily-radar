from __future__ import annotations

import httpx


def _render_item_lines(item: dict) -> list[str]:
    lines = [f"- [{item['title']}]({item['url']})"]
    if item.get("summary"):
        lines.append(f"  - 摘要：{item['summary']}")
    if item.get("why_now"):
        lines.append(f"  - 为什么现在：{item['why_now']}")
    if item.get("follow_up"):
        lines.append(f"  - 继续关注：{item['follow_up']}")
    return lines


def _render_sections(sections: list[dict]) -> list[str]:
    lines: list[str] = []
    for section in sections:
        lines.append(f"**{section['title']}**")
        for item in section.get("items", []):
            lines.extend(_render_item_lines(item))
    return lines


def _chunk_lines(lines: list[str], max_lines: int) -> list[list[str]]:
    chunks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        current.append(line)
        if len(current) >= max_lines:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def build_cards(*, title: str, sections: list[dict], metadata: dict | None = None, max_lines: int = 20) -> list[dict]:
    lines = _render_sections(sections)
    chunks = _chunk_lines(lines, max_lines=max_lines)
    cards: list[dict] = []
    for chunk_index, chunk in enumerate(chunks, start=1):
        elements = [{"tag": "markdown", "content": line} for line in chunk]
        if metadata and chunk_index == 1:
            elements.append({"tag": "markdown", "content": f"`运行信息`：{metadata}"})
        cards.append(
            {
                "msg_type": "interactive",
                "card": {
                    "config": {"wide_screen_mode": True},
                    "header": {"title": {"tag": "plain_text", "content": f"{title}（{chunk_index}/{len(chunks)}）"}},
                    "elements": elements,
                },
            }
        )
    return cards


def build_digest_cards(
    *,
    title: str,
    bundles: list[dict],
    metadata: dict | None = None,
    max_lines: int = 20,
) -> list[dict]:
    cards: list[dict] = []
    for bundle_index, bundle in enumerate(bundles):
        label = bundle["label"]
        sections = bundle.get("sections", [])
        lines = _render_sections(sections)
        chunks = _chunk_lines(lines, max_lines=max_lines)
        for chunk_index, chunk in enumerate(chunks, start=1):
            elements = [{"tag": "markdown", "content": line} for line in chunk]
            if metadata and bundle_index == 0 and chunk_index == 1:
                elements.append({"tag": "markdown", "content": f"`运行信息`：{metadata}"})
            cards.append(
                {
                    "msg_type": "interactive",
                    "card": {
                        "config": {"wide_screen_mode": True},
                        "header": {
                            "title": {
                                "tag": "plain_text",
                                "content": f"{title} · {label}（{chunk_index}/{len(chunks)}）",
                            }
                        },
                        "elements": elements,
                    },
                }
            )
    return cards


def build_alert_cards(*, title: str, message: str, metadata: dict | None = None) -> list[dict]:
    elements = [{"tag": "markdown", "content": message}]
    if metadata:
        elements.append({"tag": "markdown", "content": f"`运行信息`：{metadata}"})
    return [
        {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {"title": {"tag": "plain_text", "content": title}},
                "elements": elements,
            },
        }
    ]


def send_cards(*, webhook_url: str, cards: list[dict]) -> None:
    with httpx.Client(timeout=15.0) as client:
        for payload in cards:
            response = client.post(webhook_url, json=payload)
            response.raise_for_status()
