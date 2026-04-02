from __future__ import annotations

import httpx


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
    lines: list[str] = []
    for section in sections:
        lines.append(f"**{section['title']}**")
        for item in section.get("items", []):
            lines.append(f"- [{item['title']}]({item['url']})")
            if item.get("summary"):
                lines.append(f"  - {item['summary']}")
            if item.get("why_now"):
                lines.append(f"  - {item['why_now']}")

    chunks = _chunk_lines(lines, max_lines=max_lines)
    cards: list[dict] = []
    for chunk_index, chunk in enumerate(chunks, start=1):
        elements = [{"tag": "markdown", "content": line} for line in chunk]
        if metadata and chunk_index == 1:
            elements.append({"tag": "markdown", "content": f"`meta`: {metadata}"})
        cards.append(
            {
                "msg_type": "interactive",
                "card": {
                    "config": {"wide_screen_mode": True},
                    "header": {"title": {"tag": "plain_text", "content": f"{title} ({chunk_index}/{len(chunks)})"}},
                    "elements": elements,
                },
            }
        )
    return cards


def build_alert_cards(*, title: str, message: str, metadata: dict | None = None) -> list[dict]:
    elements = [{"tag": "markdown", "content": message}]
    if metadata:
        elements.append({"tag": "markdown", "content": f"`meta`: {metadata}"})
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
