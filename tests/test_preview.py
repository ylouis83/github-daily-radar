from datetime import date

from github_daily_radar.preview import build_preview_cards


def test_build_preview_cards_contains_all_three_tracks():
    cards = build_preview_cards(today=date(2026, 4, 16))

    assert len(cards) == 1
    card = cards[0]
    assert card["msg_type"] == "interactive"
    assert "AI Builder Radar" in card["card"]["header"]["title"]["content"]

    text_parts = []
    for element in card["card"]["elements"]:
        if element.get("tag") == "markdown":
            text_parts.append(element.get("content", ""))
        elif element.get("tag") == "column_set":
            for column in element.get("columns", []):
                for child in column.get("elements", []):
                    if child.get("tag") == "markdown":
                        text_parts.append(child.get("content", ""))

    all_text = "\n".join(text_parts)
    assert "GitHub Radar" in all_text
    assert "Tech Pulse" in all_text
    assert "Builder Watch" in all_text
    assert "Today's Focus" in all_text
    assert "Quick Scan" in all_text
    assert "2026-04-16" in all_text
