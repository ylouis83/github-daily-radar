from github_daily_radar.models import Candidate, CandidateMetrics
from github_daily_radar.summarize.digest import build_display_items, choose_daily_limit, select_top_items


def test_build_display_items_uses_kind_specific_chinese_fallbacks():
    items = build_display_items(
        [
            Candidate(
                candidate_id="repo:owner/name",
                kind="project",
                source_query="topic:agent",
                title="owner/name",
                url="https://github.com/owner/name",
                repo_full_name="owner/name",
                author="owner",
                created_at="2026-04-01T00:00:00Z",
                updated_at="2026-04-02T00:00:00Z",
                body_excerpt="an english excerpt that should not leak into the default card copy",
                topics=["agent"],
                labels=[],
                metrics=CandidateMetrics(stars=12, forks=3),
                raw_signals={},
                rule_scores={},
                dedupe_key="owner/name",
            ),
            Candidate(
                candidate_id="skill:owner/skill",
                kind="skill",
                source_query="filename:SKILL.md path:skills",
                title="owner/skill",
                url="https://github.com/owner/skill",
                repo_full_name="owner/skill",
                author="owner",
                created_at="2026-04-01T00:00:00Z",
                updated_at="2026-04-02T00:00:00Z",
                body_excerpt="english skill copy",
                topics=["agent"],
                labels=[],
                metrics=CandidateMetrics(stars=8, forks=2),
                raw_signals={},
                rule_scores={},
                dedupe_key="owner/skill",
            ),
            Candidate(
                candidate_id="discussion:owner/thread",
                kind="discussion",
                source_query="proposal",
                title="owner/thread",
                url="https://github.com/owner/name/discussions/1",
                repo_full_name="owner/name",
                author="owner",
                created_at="2026-04-01T00:00:00Z",
                updated_at="2026-04-02T00:00:00Z",
                body_excerpt="english discussion copy",
                topics=[],
                labels=[],
                metrics=CandidateMetrics(comments=15),
                raw_signals={},
                rule_scores={},
                dedupe_key="owner/thread",
            ),
        ],
        editorial=[],
    )

    assert "特点：" in items[0]["summary"]
    assert "核心能力：" in items[0]["summary"]
    assert "引入必要性：" in items[0]["summary"]
    assert "特点：" in items[1]["summary"]
    assert "核心能力：" in items[1]["summary"]
    assert "纳入必要性：" in items[1]["summary"]
    assert "焦点：" in items[2]["summary"]
    assert "核心观点：" in items[2]["summary"]
    assert "跟进必要性：" in items[2]["summary"]
    assert items[0]["summary"] != items[1]["summary"]
    assert items[0]["summary"] != items[2]["summary"]
    assert "english" not in items[0]["summary"].lower()
    assert "english" not in items[1]["summary"].lower()
    assert "english" not in items[2]["summary"].lower()
    assert "follow_up" not in items[0]


def test_build_display_items_prefers_ossinsight_trend_language():
    candidate = Candidate(
        candidate_id="project:owner/trend",
        kind="project",
        source_query="ossinsight:trending:past_24_hours",
        title="owner/trend",
        url="https://github.com/owner/trend",
        repo_full_name="owner/trend",
        author="owner",
        created_at="2026-04-01T00:00:00Z",
        updated_at="2026-04-02T00:00:00Z",
        body_excerpt="trend",
        topics=["agent"],
        labels=[],
        metrics=CandidateMetrics(stars=120, forks=10, star_growth_7d=600),
        raw_signals={},
        rule_scores={},
        dedupe_key="owner/trend",
    )

    items = build_display_items([candidate], editorial=[])

    assert "特点：" in items[0]["summary"]
    assert "热度正在持续上升" in items[0]["summary"]
    assert "核心能力：" in items[0]["summary"]
    assert "引入必要性：" in items[0]["summary"]
    assert "OSSInsight" in items[0]["why_now"]
    assert "+600⭐" in items[0]["why_now"]


def test_build_display_items_creates_distinct_project_profiles():
    candidate = Candidate(
        candidate_id="project:owner/en",
        kind="project",
        source_query="topic:agent",
        title="owner/en",
        url="https://github.com/owner/en",
        repo_full_name="owner/en",
        author="owner",
        created_at="2026-04-01T00:00:00Z",
        updated_at="2026-04-02T00:00:00Z",
        body_excerpt="english excerpt",
        topics=["agent"],
        labels=[],
        metrics=CandidateMetrics(stars=30, forks=2, star_growth_7d=250),
        raw_signals={},
        rule_scores={},
        dedupe_key="owner/en",
    )
    other_candidate = Candidate(
        candidate_id="project:owner/mcp",
        kind="project",
        source_query="topic:mcp",
        title="owner/mcp",
        url="https://github.com/owner/mcp",
        repo_full_name="owner/mcp",
        author="owner",
        created_at="2026-04-01T00:00:00Z",
        updated_at="2026-04-02T00:00:00Z",
        body_excerpt="A toolkit for MCP servers and tool use",
        topics=["mcp"],
        labels=[],
        metrics=CandidateMetrics(stars=80, forks=12, star_growth_7d=250),
        raw_signals={},
        rule_scores={},
        dedupe_key="owner/mcp",
    )

    items = build_display_items(
        [candidate, other_candidate],
        editorial=[
            {
                "title": "owner/en",
                "url": "https://github.com/owner/en",
                "kind": "project",
                "trait": "围绕终端式 AI 编程工作流",
                "capability": "把复杂编码任务拆成可执行命令",
                "necessity": "适合想把 AI 编程沉入日常开发的人",
                "why_now": "It is getting traction fast.",
            }
        ],
    )

    assert "特点：" in items[0]["summary"]
    assert "核心能力：" in items[0]["summary"]
    assert "引入必要性：" in items[0]["summary"]
    assert items[0]["summary"] != items[1]["summary"]
    assert "MCP" in items[1]["summary"] or "mcp" in items[1]["summary"].lower()
    assert "AI 编程" in items[0]["summary"]
    assert items[0]["why_now"] == "近 7 天 +250⭐"


def test_choose_daily_limit_is_dynamic_between_10_and_20():
    assert choose_daily_limit(list(range(4))) == 4
    assert choose_daily_limit(list(range(12))) == 12
    assert choose_daily_limit(list(range(24))) == 20


def test_select_top_items_is_project_first_with_repo_cap():
    items = [
        {
            "kind": "skill",
            "title": "skill-a",
            "url": "https://github.com/owner/skill-a",
            "summary": "技能",
            "repo_full_name": "owner/skill-a",
            "score": 100.0,
        },
        {
            "kind": "skill",
            "title": "skill-b",
            "url": "https://github.com/owner/skill-b",
            "summary": "技能",
            "repo_full_name": "owner/skill-b",
            "score": 90.0,
        },
        {
            "kind": "project",
            "title": "project-a",
            "url": "https://github.com/owner/project-a",
            "summary": "项目",
            "repo_full_name": "owner/project-a",
            "score": 5.0,
            "editorial_rank": 2,
        },
        {
            "kind": "discussion",
            "title": "discussion-a",
            "url": "https://github.com/owner/discussion-a",
            "summary": "讨论",
            "repo_full_name": "owner/discussion-a",
            "score": 4.0,
        },
        {
            "kind": "project",
            "title": "project-b",
            "url": "https://github.com/owner/project-b",
            "summary": "项目",
            "repo_full_name": "owner/project-b",
            "score": 3.0,
            "editorial_rank": 1,
        },
        {
            "kind": "project",
            "title": "project-a-duplicate",
            "url": "https://github.com/owner/project-a/pulls",
            "summary": "项目重复",
            "repo_full_name": "owner/project-a",
            "score": 2.0,
        },
    ]

    selected = select_top_items(items)

    assert [item["title"] for item in selected] == [
        "project-b",
        "project-a",
        "skill-a",
        "skill-b",
        "discussion-a",
    ]
    assert [item["kind"] for item in selected] == ["project", "project", "skill", "skill", "discussion"]
