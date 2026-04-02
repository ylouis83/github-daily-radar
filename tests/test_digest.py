from github_daily_radar.models import Candidate, CandidateMetrics
from github_daily_radar.summarize.digest import build_display_items, split_a_b


def test_build_display_items_uses_chinese_fallbacks():
    candidate = Candidate(
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
    )

    items = build_display_items([candidate], editorial=[])

    # 新行为：fallback 使用真实 body_excerpt，不用模板废话
    assert items[0]["summary"] == "an english excerpt that should not leak into the default card copy"
    assert "follow_up" not in items[0]


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
