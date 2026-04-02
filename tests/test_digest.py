from github_daily_radar.models import Candidate, CandidateMetrics
from github_daily_radar.summarize.digest import build_display_items


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

    assert items[0]["summary"].startswith("这是一个近期活跃的项目")
    assert "原文" not in items[0]["summary"]
    assert "最近有 12 星 / 3 个 fork" in items[0]["why_now"]
    assert items[0]["follow_up"].startswith("建议先看 README")
