from github_daily_radar.publish.feishu import build_cards, build_digest_cards


def test_build_digest_cards_creates_two_bundles_with_chinese_headers():
    sections_a = [
        {
            "title": "必看项目",
            "items": [
                {
                    "title": "owner/repo",
                    "url": "https://github.com/owner/repo",
                    "summary": "中文摘要",
                    "why_now": "值得关注",
                }
            ],
        }
    ]
    sections_b = [
        {
            "title": "项目补充",
            "items": [
                {
                    "title": "owner/other",
                    "url": "https://github.com/owner/other",
                    "summary": "补充摘要",
                }
            ],
        }
    ]

    cards = build_digest_cards(
        title="GitHub 每日雷达",
        bundles=[
            {"label": "A 精编版", "sections": sections_a},
            {"label": "B 保留版", "sections": sections_b},
        ],
        metadata={"count": 2},
        max_lines=20,
    )

    assert len(cards) == 2
    header_a = cards[0]["card"]["header"]["title"]["content"]
    header_b = cards[1]["card"]["header"]["title"]["content"]
    assert "A 精编版" in header_a
    assert "B 保留版" in header_b
    assert "每日雷达" in header_a
    elements = [element["content"] for element in cards[0]["card"]["elements"]]
    assert any("摘要：" in content for content in elements)
    assert any("为什么现在：" in content for content in elements)


def test_build_cards_keeps_chinese_labels():
    sections = [
        {
            "title": "必看技能",
            "items": [
                {
                    "title": "owner/skill",
                    "url": "https://github.com/owner/skill",
                    "summary": "中文摘要",
                }
            ],
        }
    ]

    cards = build_cards(title="GitHub 每日雷达", sections=sections, metadata={"count": 1}, max_lines=20)

    assert len(cards) == 1
    header = cards[0]["card"]["header"]["title"]["content"]
    assert "每日雷达" in header
    elements = [element["content"] for element in cards[0]["card"]["elements"]]
    assert any("摘要：" in content for content in elements)
