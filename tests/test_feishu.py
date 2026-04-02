from datetime import date

from github_daily_radar.publish.feishu import build_digest_card, build_alert_cards


def test_build_digest_card_single_card_with_sections():
    items = [
        {
            "kind": "project",
            "title": "owner/repo",
            "url": "https://github.com/owner/repo",
            "summary": "一个很酷的项目",
            "stars": 1200,
            "star_delta_1d": 300,
            "star_velocity": "surge",
        },
        {
            "kind": "skill",
            "title": "owner/skill",
            "url": "https://github.com/owner/skill",
            "summary": "Claude Code 的 skill 框架",
            "stars": 5000,
            "star_delta_1d": 0,
            "star_velocity": "",
        },
        {
            "kind": "discussion",
            "title": "RFC: 新架构提案",
            "url": "https://github.com/org/repo/discussions/123",
            "summary": "讨论新的 Agent 运行时架构",
            "stars": 0,
            "star_delta_1d": 0,
            "star_velocity": "",
        },
    ]

    card = build_digest_card(items=items, metadata={"count": 50, "a_count": 3}, today=date(2026, 4, 2))

    assert card["msg_type"] == "interactive"
    header = card["card"]["header"]["title"]["content"]
    assert "每日雷达" in header
    assert "2026-04-02" in header
    assert card["card"]["header"]["template"] == "blue"

    contents = [el.get("content", "") for el in card["card"]["elements"] if el.get("tag") == "markdown"]
    all_text = "\n".join(contents)

    # 验证概览
    assert "3 条" in all_text or "今日精选" in all_text
    # 验证分区标题
    assert "🚀 热门项目" in all_text
    assert "🧩 发现技能" in all_text
    assert "💬 提案与讨论" in all_text
    # 验证链接可点击
    assert "[owner/repo](https://github.com/owner/repo)" in all_text
    # 验证 star badge
    assert "🔥+300⭐" in all_text
    # 验证真实摘要（不是模板）
    assert "一个很酷的项目" in all_text
    # 验证卡片不再渲染运行信息
    assert "📊" not in all_text
    assert "🔍" not in all_text
    assert "运行信息" not in all_text
    assert "2026-04-02" in all_text


def test_build_digest_card_fuses_primary_and_secondary_sections():
    primary_items = [
        {
            "kind": "project",
            "title": "owner/repo-a",
            "url": "https://github.com/owner/repo-a",
            "summary": "主卡项目",
            "stars": 100,
            "star_delta_1d": 0,
            "star_velocity": "",
        }
    ]
    secondary_items = [
        {
            "kind": "skill",
            "title": "owner/skill-b",
            "url": "https://github.com/owner/skill-b",
            "summary": "补充技能",
            "stars": 42,
            "star_delta_1d": 0,
            "star_velocity": "",
        }
    ]

    card = build_digest_card(
        items=primary_items,
        secondary_items=secondary_items,
        today=date(2026, 4, 2),
    )

    contents = [el.get("content", "") for el in card["card"]["elements"] if el.get("tag") == "markdown"]
    all_text = "\n".join(contents)

    assert "A 精编版" in all_text
    assert "B 保留版" in all_text
    assert "owner/repo-a" in all_text
    assert "owner/skill-b" in all_text
    assert isinstance(card, dict)


def test_build_digest_card_empty_discussion_omits_section():
    items = [
        {
            "kind": "project",
            "title": "test/repo",
            "url": "https://github.com/test/repo",
            "summary": "desc",
            "stars": 100,
            "star_delta_1d": 0,
            "star_velocity": "",
        },
    ]

    card = build_digest_card(items=items, today=date(2026, 4, 2))

    contents = [el.get("content", "") for el in card["card"]["elements"] if el.get("tag") == "markdown"]
    all_text = "\n".join(contents)
    # 空分区直接不渲染，不显示"提案与讨论"标题
    assert "提案与讨论" not in all_text


def test_build_digest_card_is_single_card():
    """确保不管多少条目都只生成 1 张卡片"""
    items = [
        {
            "kind": "project",
            "title": f"org/repo-{i}",
            "url": f"https://github.com/org/repo-{i}",
            "summary": f"Project {i}",
            "stars": i * 100,
            "star_delta_1d": 0,
            "star_velocity": "",
        }
        for i in range(20)
    ]

    card = build_digest_card(items=items, today=date(2026, 4, 2))

    # 返回的是单个 dict，不是 list
    assert isinstance(card, dict)
    assert card["msg_type"] == "interactive"


def test_build_digest_card_truncates_without_cutting_middle_of_token():
    items = [
        {
            "kind": "project",
            "title": "owner/repo",
            "url": "https://github.com/owner/repo",
            "summary": "freeandopensource" + ("x" * 74) + "-copy-pasteautomationwithbrowserworkflowsandlongdescriptionsdesignedtooverflowthecardandforceboundaryhandling",
            "stars": 100,
            "star_delta_1d": 0,
            "star_velocity": "",
        }
    ]

    card = build_digest_card(items=items, today=date(2026, 4, 2))
    contents = [el.get("content", "") for el in card["card"]["elements"] if el.get("tag") == "markdown"]
    all_text = "\n".join(contents)

    assert "copy-pa" not in all_text
    assert "…" in all_text


def test_alert_card_has_red_theme():
    cards = build_alert_cards(title="Alert", message="Something failed")

    assert len(cards) == 1
    assert cards[0]["card"]["header"]["template"] == "red"
    contents = [el.get("content", "") for el in cards[0]["card"]["elements"]]
    assert any("Something failed" in c for c in contents)


def test_star_badge_renders_k_format():
    """大 star 数应显示为 ⭐131K"""
    items = [
        {
            "kind": "skill",
            "title": "big/repo",
            "url": "https://github.com/big/repo",
            "summary": "大仓库",
            "stars": 131000,
            "star_delta_1d": 0,
            "star_velocity": "",
        },
    ]

    card = build_digest_card(items=items, today=date(2026, 4, 2))
    contents = [el.get("content", "") for el in card["card"]["elements"] if el.get("tag") == "markdown"]
    all_text = "\n".join(contents)
    assert "⭐131K" in all_text
