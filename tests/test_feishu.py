from datetime import date

import httpx
import pytest

import github_daily_radar.publish.feishu as feishu_module
from github_daily_radar.publish.feishu import build_digest_card, build_alert_cards, send_cards


def _collect_card_text(card: dict) -> str:
    contents = [el.get("content", "") for el in card["card"]["elements"] if el.get("tag") == "markdown"]
    for el in card["card"]["elements"]:
        if el.get("tag") == "column_set":
            for col in el.get("columns", []):
                for sub_el in col.get("elements", []):
                    if sub_el.get("tag") == "markdown":
                        contents.append(sub_el.get("content", ""))
    return "\n".join(contents)


def test_build_digest_card_single_card_with_sections():
    items = [
        {
            "kind": "project",
            "title": "owner/repo",
            "url": "https://github.com/owner/repo",
            "trait": "终端原生的智能编码代理",
            "capability": "通过自然语言命令执行任务",
            "necessity": "提升编码效率",
            "summary": "一个很酷的项目",
            "why_now": "今日趋势热度极高",
            "stars": 1200,
            "star_delta_1d": 300,
            "star_velocity": "surge",
        },
        {
            "kind": "skill",
            "title": "owner/skill",
            "url": "https://github.com/owner/skill",
            "trait": "Claude Code 的 skill 框架",
            "capability": "把可复用的提示词沉淀成资产",
            "necessity": "适合纳入技能库",
            "summary": "Claude Code 的 skill 框架",
            "stars": 5000,
            "star_delta_1d": 0,
            "star_velocity": "",
        },
        {
            "kind": "discussion",
            "title": "RFC: 新架构提案",
            "url": "https://github.com/org/repo/discussions/123",
            "trait": "讨论新的 Agent 运行时架构",
            "capability": "聚焦方案取舍",
            "necessity": "值得跟进结论",
            "summary": "讨论新的 Agent 运行时架构",
            "stars": 0,
            "star_delta_1d": 0,
            "star_velocity": "",
        },
    ]

    card = build_digest_card(items=items, metadata={"count": 50}, today=date(2026, 4, 2))

    assert card["msg_type"] == "interactive"
    header = card["card"]["header"]["title"]["content"]
    assert "AI Builder Radar" in header
    assert "2026-04-02" in header
    assert card["card"]["header"]["template"] == "indigo"

    contents = [el.get("content", "") for el in card["card"]["elements"] if el.get("tag") == "markdown"]
    # 也提取 column_set 内嵌的 markdown 文本
    for el in card["card"]["elements"]:
        if el.get("tag") == "column_set":
            for col in el.get("columns", []):
                for sub_el in col.get("elements", []):
                    if sub_el.get("tag") == "markdown":
                        contents.append(sub_el.get("content", ""))
    all_text = "\n".join(contents)

    # 验证概览面板（column_set 或文字版）
    assert "50" in all_text  # 候选总数
    assert "3" in all_text  # 精选数（3 条）
    # 不再有 A/B 标签
    assert "🅰️" not in all_text
    assert "🅱️" not in all_text
    # 验证分区标题
    assert "🚀 核心 AI 项目" in all_text
    assert "🧩 MCP & Skills" in all_text
    assert "💬 提案与讨论" in all_text
    # 验证链接可点击
    assert "[owner/repo](https://github.com/owner/repo)" in all_text
    # 验证 star badge
    assert "🔥+300⭐" in all_text
    # 验证画像字段分行显示
    assert "▸ 特点：" in all_text
    assert "▸ 核心能力：" in all_text
    assert "2026-04-02" in all_text


def test_build_digest_card_renders_github_tech_and_builder_tracks():
    card = build_digest_card(
        items=[
            {
                "kind": "project",
                "title": "owner/repo",
                "url": "https://github.com/owner/repo",
                "summary": "repo",
                "stars": 120,
                "star_delta_1d": 0,
                "star_velocity": "",
            }
        ],
        tech_items=[
            {
                "title": "Claude Code pager",
                "url": "https://www.producthunt.com/r/1",
                "source_label": "Product Hunt",
                "why_now": "开发者工具热度很高",
            }
        ],
        builder_sections={
            "x": [
                {
                    "title": "Swyx",
                    "url": "https://x.com/swyx/status/1",
                    "why_now": "Builder 线程值得看",
                }
            ]
        },
        today=date(2026, 4, 16),
    )

    all_text = _collect_card_text(card)
    assert "GitHub Radar" in all_text
    assert "Tech Pulse" in all_text
    assert "Builder Watch" in all_text
    assert "今天最值得打开的项目、技能与讨论" in all_text
    assert "今天值得知道的外部科技信号" in all_text
    assert "今天谁值得跟进，哪些内容值得点开" in all_text
    assert "Product Hunt" in all_text
    assert "Swyx" in all_text


def test_build_digest_card_uses_structured_profile():
    """画像的三个字段应各自独立一行"""
    items = [
        {
            "kind": "project",
            "title": "owner/repo",
            "url": "https://github.com/owner/repo",
            "trait": "围绕终端式 AI 编程工作流",
            "capability": "把复杂编码任务拆成可执行命令",
            "necessity": "适合想把 AI 编程沉入日常开发的人",
            "why_now": "OSSInsight 近期热度上升",
            "stars": 1200,
            "star_delta_1d": 300,
            "star_velocity": "surge",
        },
        {
            "kind": "skill",
            "title": "owner/skill",
            "url": "https://github.com/owner/skill",
            "trait": "可复用的技能资源",
            "capability": "沉淀成工作流",
            "necessity": "值得收藏",
            "why_now": "适合纳入技能库",
            "stars": 5000,
            "star_delta_1d": 0,
            "star_velocity": "",
        },
        {
            "kind": "discussion",
            "title": "RFC: 新架构提案",
            "url": "https://github.com/org/repo/discussions/123",
            "trait": "焦点明确的讨论",
            "capability": "核心观点清晰",
            "necessity": "值得跟进",
            "why_now": "评论活跃",
            "stars": 0,
            "star_delta_1d": 0,
            "star_velocity": "",
        },
    ]

    card = build_digest_card(items=items, today=date(2026, 4, 2))
    contents = [el.get("content", "") for el in card["card"]["elements"] if el.get("tag") == "markdown"]
    all_text = "\n".join(contents)

    # 验证 project 精编画像三段分行
    assert "▸ 特点：" in all_text
    assert "▸ 核心能力：" in all_text
    assert "▸ 引入必要性：" in all_text
    # skill 区精简模式：仅保留 trait 一行
    assert "▸ 特点：可复用的技能资源" in all_text
    # discussion 精编模式：焦点 + 核心观点 + 跟进必要性
    assert "▸ 焦点：" in all_text
    assert "▸ 核心观点：" in all_text
    assert "▸ 跟进必要性：" in all_text


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
    assert "提案与讨论" not in all_text
    assert "MCP & Skills" not in all_text  # 没有 skill 条目也不渲染


def test_build_digest_card_can_render_non_project_sections_first():
    items = [
        {
            "kind": "project",
            "title": "owner/project",
            "url": "https://github.com/owner/project",
            "summary": "project",
            "stars": 100,
            "star_delta_1d": 0,
            "star_velocity": "",
        },
        {
            "kind": "skill",
            "title": "owner/skill",
            "url": "https://github.com/owner/skill",
            "summary": "skill",
            "stars": 50,
            "star_delta_1d": 0,
            "star_velocity": "",
        },
        {
            "kind": "discussion",
            "title": "owner/discussion",
            "url": "https://github.com/owner/repo/discussions/1",
            "summary": "discussion",
            "stars": 0,
            "star_delta_1d": 0,
            "star_velocity": "",
        },
    ]

    card = build_digest_card(items=items, project_first=False, today=date(2026, 4, 2))
    contents = [el.get("content", "") for el in card["card"]["elements"] if el.get("tag") == "markdown"]
    all_text = "\n".join(contents)

    assert all_text.index("🧩 MCP & Skills") < all_text.index("🚀 核心 AI 项目")
    assert all_text.index("💬 提案与讨论") < all_text.index("🚀 核心 AI 项目")


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
    assert isinstance(card, dict)
    assert card["msg_type"] == "interactive"


def test_build_digest_card_keeps_full_project_profiles_for_larger_lists():
    items = [
        {
            "kind": "project",
            "title": f"org/repo-{i}",
            "url": f"https://github.com/org/repo-{i}",
            "trait": f"项目 {i} 的独特特点",
            "capability": f"项目 {i} 的核心能力",
            "necessity": f"项目 {i} 的引入必要性",
            "summary": f"Project {i}",
            "why_now": f"Why now {i}",
            "stars": 100 + i,
            "star_delta_1d": 0,
            "star_velocity": "",
        }
        for i in range(6)
    ]

    card = build_digest_card(items=items, today=date(2026, 4, 2))
    contents = [el.get("content", "") for el in card["card"]["elements"] if el.get("tag") == "markdown"]
    all_text = "\n".join(contents)

    assert "Quick Scan" in all_text
    assert all_text.count("▸ 特点：") == 4
    assert all_text.count("▸ 核心能力：") == 4
    assert all_text.count("▸ 引入必要性：") == 4


def test_alert_card_has_red_theme():
    cards = build_alert_cards(title="Alert", message="Something failed")
    assert len(cards) == 1
    assert cards[0]["card"]["header"]["template"] == "red"
    contents = [el.get("content", "") for el in cards[0]["card"]["elements"]]
    assert any("Something failed" in c for c in contents)


def test_star_badge_renders_k_format():
    """大 star 数应显示为 ⭐131.0K"""
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
    assert "⭐131.0K" in all_text


def test_footer_only_shows_date():
    """Footer 只保留日期，不再展示运行时指标"""
    items = [
        {
            "kind": "project",
            "title": "test/repo",
            "url": "https://github.com/test/repo",
            "summary": "desc",
            "stars": 10,
            "star_delta_1d": 0,
            "star_velocity": "",
        },
    ]

    metadata = {
        "count": 78,
        "editorial": 5,
        "api_usage": {"search_used": 18, "graphql_used": 11},
    }
    card = build_digest_card(items=items, metadata=metadata, today=date(2026, 4, 2))
    contents = [el.get("content", "") for el in card["card"]["elements"] if el.get("tag") == "markdown"]
    all_text = "\n".join(contents)

    assert "📅 2026-04-02" in all_text
    assert "候选 78" not in all_text
    assert "LLM 精编 5" not in all_text
    assert "Search 18" not in all_text
    assert "GraphQL 11" not in all_text


def test_build_digest_card_backward_compat_secondary_items():
    """传入 secondary_items 时应自动合并去重"""
    primary = [
        {
            "candidate_id": "project:owner/primary",
            "kind": "project",
            "title": "owner/primary",
            "url": "https://github.com/owner/primary",
            "repo_full_name": "owner/primary",
            "summary": "主版",
            "stars": 100,
            "star_delta_1d": 0,
            "star_velocity": "",
        }
    ]
    secondary = [
        {
            "kind": "skill",
            "candidate_id": "skill:owner/skill-b",
            "title": "owner/skill-b",
            "url": "https://github.com/owner/skill-b",
            "repo_full_name": "owner/skill-b",
            "summary": "补充技能",
            "stars": 42,
            "star_delta_1d": 0,
            "star_velocity": "",
        },
        {
            "kind": "discussion",
            "candidate_id": "discussion:owner/primary/1",
            "title": "owner/primary discussion",
            "url": "https://github.com/owner/primary/discussions/1",
            "repo_full_name": "owner/primary",
            "summary": "同仓库讨论",
            "stars": 0,
            "star_delta_1d": 0,
            "star_velocity": "",
        },
        {
            "kind": "project",
            "title": "owner/primary",
            "url": "https://github.com/owner/primary",
            "repo_full_name": "owner/primary",
            "summary": "重复",
            "stars": 100,
            "star_delta_1d": 0,
            "star_velocity": "",
        },
    ]

    card = build_digest_card(items=primary, secondary_items=secondary, today=date(2026, 4, 2))
    contents = [el.get("content", "") for el in card["card"]["elements"] if el.get("tag") == "markdown"]
    all_text = "\n".join(contents)

    assert "owner/primary" in all_text
    assert "owner/skill-b" in all_text
    assert "owner/primary/discussions/1" in all_text
    # primary 不应出现两次，但同仓库的讨论条目仍应保留
    assert all_text.count("[owner/primary]") == 1


class _StubClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = list(responses)
        self.posts: list[tuple[str, dict]] = []

    def __enter__(self) -> "_StubClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def post(self, url: str, json: dict) -> httpx.Response:
        self.posts.append((url, json))
        return self._responses.pop(0)


def test_send_cards_raises_when_feishu_returns_business_error(monkeypatch):
    client = _StubClient(
        [
            httpx.Response(
                200,
                json={"code": 19024, "msg": "message too large"},
                request=httpx.Request("POST", "https://example.com/hook"),
            )
        ]
    )
    monkeypatch.setattr(feishu_module.httpx, "Client", lambda *args, **kwargs: client)

    with pytest.raises(RuntimeError, match="message too large"):
        send_cards(
            webhook_url="https://example.com/hook",
            cards=[{"msg_type": "interactive", "card": {"elements": []}}],
        )


def test_send_cards_accepts_successful_feishu_response(monkeypatch):
    client = _StubClient(
        [
            httpx.Response(
                200,
                json={"code": 0, "msg": "ok"},
                request=httpx.Request("POST", "https://example.com/hook"),
            )
        ]
    )
    monkeypatch.setattr(feishu_module.httpx, "Client", lambda *args, **kwargs: client)

    send_cards(
        webhook_url="https://example.com/hook",
        cards=[{"msg_type": "interactive", "card": {"elements": []}}],
    )

    assert client.posts[0][0] == "https://example.com/hook"
