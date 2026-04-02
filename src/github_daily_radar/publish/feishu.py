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


def _render_section_block(section: dict) -> str:
    lines = [f"**{section['title']}**"]
    lines.extend(section.get("lines", []))
    for item in section.get("items", []):
        lines.extend(_render_item_lines(item))
    return "\n".join(lines)


def _render_sections(sections: list[dict]) -> list[str]:
    blocks: list[str] = []
    for section in sections:
        blocks.append(_render_section_block(section))
    return blocks


def _chunk_blocks(blocks: list[str], max_blocks: int) -> list[list[str]]:
    chunks: list[list[str]] = []
    current: list[str] = []
    for block in blocks:
        current.append(block)
        if len(current) >= max_blocks:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def build_cards(*, title: str, sections: list[dict], metadata: dict | None = None, max_lines: int = 20) -> list[dict]:
    blocks = _render_sections(sections)
    chunks = _chunk_blocks(blocks, max_blocks=max_lines)
    cards: list[dict] = []
    for chunk_index, chunk in enumerate(chunks, start=1):
        elements = [{"tag": "markdown", "content": line} for line in chunk]
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
        blocks = _render_sections(sections)
        chunks = _chunk_blocks(blocks, max_blocks=max_lines)
        for chunk_index, chunk in enumerate(chunks, start=1):
            elements = [{"tag": "markdown", "content": line} for line in chunk]
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
