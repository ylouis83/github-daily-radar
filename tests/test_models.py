from github_daily_radar.models import Candidate, CandidateMetrics


def test_candidate_keeps_required_fields():
    candidate = Candidate(
        candidate_id="repo:owner/name",
        kind="project",
        source_query="topic:agent created:>2026-03-26",
        title="owner/name",
        url="https://github.com/owner/name",
        repo_full_name="owner/name",
        author="owner",
        created_at="2026-04-01T00:00:00Z",
        updated_at="2026-04-02T00:00:00Z",
        body_excerpt="A useful repo",
        topics=["agent"],
        labels=[],
        metrics=CandidateMetrics(stars=120, forks=8, comments=0, reactions=0, star_growth_7d=30),
        raw_signals={"source": "search"},
        rule_scores={"novelty": 0.4, "signal": 0.5, "utility": 0.6, "taste": 0.2},
        dedupe_key="owner/name",
    )

    assert candidate.kind == "project"
    assert candidate.metrics.stars == 120
