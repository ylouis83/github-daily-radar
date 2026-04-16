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
    assert "GitHub 主榜" in all_text
    assert "科技热讯" in all_text
    assert "Builder Watch" in all_text
    assert "主榜" in all_text
    assert "热讯" in all_text
    assert "观察" in all_text
    assert "主题" in all_text
    assert "GitHub 主榜 · 科技热讯 · Builder Watch" in all_text
    assert "<text_tag color='blue'>主线</text_tag>" in all_text
    assert "关注主题" in all_text
    assert "延伸速览" in all_text
    assert "Podcast" in all_text
    assert "Video / Podcast" not in all_text
    assert "**Momentum Leaders · 2**" in all_text
    assert "**X · 2**" in all_text
    assert "**Podcast · 1**" in all_text
    assert "**Blog · 1**" in all_text
    assert "<link icon='platform_outlined' url='https://github.com'>GitHub</link>" in all_text
    assert "<link icon='file-link-video_outlined' url='https://www.youtube.com'>YouTube</link>" in all_text
    assert "2026-04-16" in all_text


def test_build_preview_cards_can_render_style_only_review_mode():
    cards = build_preview_cards(today=date(2026, 4, 16), style_only=True)

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
    assert "GitHub 主榜" in all_text
    assert "科技热讯" in all_text
    assert "Builder Watch" in all_text
    assert "样式预览" in all_text
    assert "仅预览卡片样式，不加载实时内容" in all_text
    assert "主榜" in all_text
    assert "主题" in all_text
    assert "anthropics/claude-code-desktop" not in all_text
    assert "Claude Code Routines" not in all_text
    assert "Swyx" not in all_text
