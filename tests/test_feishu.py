from datetime import date

import httpx
import pytest

import github_daily_radar.publish.feishu as feishu_module
from github_daily_radar.publish.feishu import build_digest_card, build_alert_cards, send_cards


def _collect_card_text(card: dict) -> str:
    contents = []
    for el in card["card"]["elements"]:
        if el.get("tag") == "markdown":
            contents.append(el.get("content", ""))
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

    all_text = _collect_card_text(card)

    # 顶部只保留副标题，不再展示四格概览和关注主题
    assert card["card"]["elements"][0]["content"] == "GitHub 主榜 · 科技热讯 · Builder Watch"
    assert card["card"]["elements"][1]["tag"] == "hr"
    assert "关注主题" not in all_text
    assert "<text_tag color='blue'>主线</text_tag>" in all_text
    assert "GitHub 主榜 · 科技热讯 · Builder Watch" in all_text
    # 不再有 A/B 标签
    assert "🅰️" not in all_text
    assert "🅱️" not in all_text
    # 验证分区标题
    assert "核心项目" in all_text
    assert "技能与 MCP" in all_text
    assert "讨论与提案" in all_text
    # 验证链接可点击
    assert "[owner/repo](https://github.com/owner/repo)" in all_text
    # 验证来源与更克制的 badge
    assert "<link icon='platform_outlined' url='https://github.com'>GitHub</link>" in all_text
    assert "+300⭐" in all_text
    # 验证画像字段分行显示
    assert "▸ 定位：" in all_text
    assert "▸ 能力：" in all_text
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
                    "title": "Swyx：围绕「agent workbench」的一线观察",
                    "url": "https://x.com/swyx/status/1",
                    "creator": "Swyx",
                    "why_now": "Builder 线程值得看",
                }
            ]
        },
        metadata={"count": 42},
        today=date(2026, 4, 16),
    )

    all_text = _collect_card_text(card)
    assert "GitHub 主榜" in all_text
    assert "科技热讯" in all_text
    assert "Builder Watch" in all_text
    assert "关注主题" not in all_text
    assert "开源仓库、技能资产与讨论线索" in all_text
    assert "发布动态、工程信号与外部热点" in all_text
    assert "创作者观点、播客与长文解读" in all_text
    assert "GitHub 主榜 · 科技热讯 · Builder Watch" in all_text
    assert "<text_tag color='blue'>主线</text_tag>" in all_text
    assert "<text_tag color='orange'>外部</text_tag>" in all_text
    assert "<text_tag color='green'>人物</text_tag>" in all_text
    assert "Product Hunt" in all_text
    assert "Swyx" in all_text
    assert "<link icon='internet_outlined' url='https://www.producthunt.com/r/1'>Product Hunt</link>" in all_text
    assert "信号：" in all_text
    assert "**X**  ·  <link icon='internet_outlined' url='https://x.com'>X</link>" in all_text
    assert "**X · 1**" not in all_text


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
    assert "▸ 定位：" in all_text
    assert "▸ 能力：" in all_text
    assert "▸ 价值：" in all_text
    # skill 区精简模式：仅保留 trait 一行
    assert "▸ 定位：可复用的技能资源" in all_text
    # discussion 精编模式：焦点 + 核心观点 + 跟进必要性
    assert "▸ 议题：" in all_text
    assert "▸ 结论：" in all_text
    assert "▸ 影响：" in all_text


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
    assert "讨论与提案" not in all_text
    assert "技能与 MCP" not in all_text  # 没有 skill 条目也不渲染


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

    assert all_text.index("技能与 MCP") < all_text.index("核心项目")
    assert all_text.index("讨论与提案") < all_text.index("核心项目")


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

    assert "延伸速览" in all_text
    assert all_text.count("▸ 定位：") == 4
    assert all_text.count("▸ 能力：") == 4
    assert all_text.count("▸ 价值：") == 4


def test_compact_items_inline_source_link_without_prefix():
    items = [
        {
            "kind": "project",
            "title": f"org/repo-{i}",
            "url": f"https://github.com/org/repo-{i}",
            "summary": f"Project {i}",
            "stars": 100 + i,
            "star_delta_1d": 0,
            "star_velocity": "",
        }
        for i in range(5)
    ]

    card = build_digest_card(items=items, today=date(2026, 4, 2))
    all_text = _collect_card_text(card)

    assert "**延伸速览**" in all_text
    assert "·  <link icon='platform_outlined' url='https://github.com/org/repo-4'>GitHub</link>" not in all_text
    assert "来源：" not in all_text


def test_compact_scan_is_trimmed_and_uses_bullets():
    items = [
        {
            "kind": "project",
            "title": f"org/repo-{i}",
            "url": f"https://github.com/org/repo-{i}",
            "summary": f"Project {i}",
            "stars": 100 + i,
            "star_delta_1d": 0,
            "star_velocity": "",
        }
        for i in range(9)
    ]

    card = build_digest_card(items=items, today=date(2026, 4, 2))
    all_text = _collect_card_text(card)

    assert "**延伸速览**" in all_text
    assert "- [org/repo-4](https://github.com/org/repo-4)  104⭐" in all_text
    assert "- [org/repo-5](https://github.com/org/repo-5)  105⭐" in all_text
    assert "- [org/repo-6](https://github.com/org/repo-6)  106⭐" in all_text
    assert "[org/repo-7](https://github.com/org/repo-7)" not in all_text
    assert "[org/repo-8](https://github.com/org/repo-8)" not in all_text
    assert "另有 2 个项目未展开" in all_text
    assert "**5.** [org/repo-4](https://github.com/org/repo-4)" not in all_text


def test_surge_and_builder_subsections_surface_counts():
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
        surge_items=[
            {
                "title": "owner/repo",
                "url": "https://github.com/owner/repo",
                "repo_full_name": "owner/repo",
                "surge_daily_delta": 300,
                "stars": 1200,
            },
            {
                "title": "owner/repo-2",
                "url": "https://github.com/owner/repo-2",
                "repo_full_name": "owner/repo-2",
                "surge_daily_delta": 180,
                "stars": 2400,
            },
        ],
        builder_sections={
            "x": [
                {"title": "Swyx", "url": "https://x.com/swyx/status/1", "why_now": "thread"},
                {"title": "Latent", "url": "https://x.com/latent/status/1", "why_now": "thread"},
            ],
            "podcast": [
                {"title": "Training Data", "url": "https://youtube.com/watch?v=1", "why_now": "podcast"}
            ],
            "blog": [
                {"title": "Claude Blog", "url": "https://claude.com/blog/1", "why_now": "blog"}
            ],
        },
        today=date(2026, 4, 2),
    )

    all_text = _collect_card_text(card)

    assert "**热度跃升**" in all_text
    assert "**热度跃升 · 2**" not in all_text
    assert all_text.index("**GitHub 主榜**") < all_text.index("**热度跃升**") < all_text.index("**核心项目**")
    assert "**X**" in all_text
    assert "**X · 2**" not in all_text
    assert "**播客**" in all_text
    assert "**播客 · 1**" not in all_text
    assert "**长文**" in all_text
    assert "**长文 · 1**" not in all_text


def test_build_digest_card_uses_group_level_source_links_for_single_source_sections():
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
        builder_sections={
            "x": [
                {
                    "title": "Claude：围绕「desktop redesign」的一线观察",
                    "url": "https://x.com/claude/status/1",
                    "creator": "Claude",
                    "why_now": "围绕「desktop redesign」，给出一线观察。",
                },
                {
                    "title": "Swyx：围绕「agent workbench」的一线观察",
                    "url": "https://x.com/swyx/status/1",
                    "creator": "Swyx",
                    "why_now": "围绕「agent workbench」，给出一线观察。",
                },
            ],
            "podcast": [
                {
                    "title": "Training Data：聊「From SEO to Agent-Led Growth」",
                    "url": "https://www.youtube.com/watch?v=1",
                    "creator": "Training Data",
                    "why_now": "围绕「From SEO to Agent-Led Growth」，展开完整对谈。",
                }
            ],
        },
        today=date(2026, 4, 2),
    )

    all_text = _collect_card_text(card)

    assert all_text.count("<link icon='internet_outlined' url='https://x.com'>X</link>") == 1
    assert "<link icon='internet_outlined' url='https://x.com/claude/status/1'>X</link>" not in all_text
    assert "<link icon='internet_outlined' url='https://x.com/swyx/status/1'>X</link>" not in all_text
    assert all_text.count("<link icon='file-link-video_outlined' url='https://www.youtube.com'>YouTube</link>") == 1


def test_alert_card_has_red_theme():
    cards = build_alert_cards(title="Alert", message="Something failed")
    assert len(cards) == 1
    assert cards[0]["card"]["header"]["template"] == "red"
    contents = [el.get("content", "") for el in cards[0]["card"]["elements"]]
    assert any("Something failed" in c for c in contents)


def test_star_badge_renders_k_format():
    """大 star 数应显示为 131.0K⭐"""
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
    assert "131.0K⭐" in all_text


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

    assert "日期  ·  2026-04-02" in all_text
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
