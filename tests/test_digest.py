from github_daily_radar.models import Candidate, CandidateMetrics
from github_daily_radar.summarize.digest import build_display_items, split_a_b


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

    assert items[0]["summary"] == "这是一个值得快速浏览的仓库，先看 README 和最近提交。"
    assert "可复用的 skill / prompt / rules 资源" in items[1]["summary"]
    assert "值得跟进的提案或讨论" in items[2]["summary"]
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

    assert "OSSInsight" in items[0]["summary"]
    assert "热度" in items[0]["summary"]


def test_split_a_b_keeps_kind_diversity():
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
        },
        {
            "kind": "discussion",
            "title": "discussion-a",
            "url": "https://github.com/owner/discussion-a",
            "summary": "讨论",
            "repo_full_name": "owner/discussion-a",
            "score": 4.0,
        },
    ]

    a_items, b_items = split_a_b(items, a_max=3, a_min=3, b_max=1, b_min=0)

    assert {item["kind"] for item in a_items} >= {"project", "skill", "discussion"}
    assert len(b_items) == 1
