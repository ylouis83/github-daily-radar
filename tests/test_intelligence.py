from github_daily_radar.intelligence import enrich_radar_context
from github_daily_radar.models import BuilderSignal, Candidate, CandidateMetrics, ExternalTechCandidate


def _candidate(
    candidate_id: str,
    *,
    kind: str = "project",
    repo_full_name: str,
    title: str | None = None,
    author: str | None = None,
    source_query: str = "query",
    raw_signals: dict | None = None,
) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        kind=kind,
        source_query=source_query,
        title=title or repo_full_name,
        url=f"https://github.com/{repo_full_name}",
        repo_full_name=repo_full_name,
        author=author or repo_full_name.split("/", 1)[0],
        created_at="2026-04-01T00:00:00Z",
        updated_at="2026-04-02T00:00:00Z",
        body_excerpt="repo",
        topics=[],
        labels=[],
        metrics=CandidateMetrics(stars=100, star_growth_7d=60),
        raw_signals=raw_signals or {},
        rule_scores={},
        dedupe_key=repo_full_name,
    )


def test_enrich_radar_context_adds_cross_source_cluster_signal():
    trending = _candidate(
        "trending:owner/repo",
        repo_full_name="owner/repo",
        raw_signals={"trending_item": {"repo_name": "owner/repo"}},
        source_query="github-trending:daily",
    )
    ossinsight = _candidate(
        "project:owner/repo",
        repo_full_name="owner/repo",
        raw_signals={"ossinsight_item": {"repo_name": "owner/repo"}},
        source_query="ossinsight:trending:past_24_hours",
    )
    tech = ExternalTechCandidate(
        source="producthunt",
        title="owner/repo",
        url="https://example.com/owner-repo",
        summary="launching owner/repo",
        score=80,
        comments=10,
        tags=[],
        published_at="2026-04-10T00:00:00Z",
    )
    signal = BuilderSignal(
        source="x",
        section="x",
        title="owner/repo ships new agent shell",
        url="https://x.com/owner/status/1",
        creator="owner",
        summary="People are discussing owner/repo",
        score=120,
        published_at="2026-04-10T00:00:00Z",
    )

    enrichment = enrich_radar_context(
        candidates=[trending, ossinsight],
        tech_candidates=[tech],
        builder_signals=[signal],
    )

    enriched = enrichment.candidates[0]
    cluster = enriched.raw_signals["cluster"]

    assert "Trending" in cluster["source_labels"]
    assert "OSSInsight" in cluster["source_labels"]
    assert "Product Hunt" in cluster["source_labels"]
    assert "Builder X" in cluster["source_labels"]
    assert enriched.rule_scores["cluster_source_count"] >= 4


def test_enrich_radar_context_builds_maintainer_items_from_multi_repo_owner():
    repo_a = _candidate(
        "project:acme/repo-a",
        repo_full_name="acme/repo-a",
        raw_signals={"ossinsight_item": {"repo_name": "acme/repo-a"}},
        source_query="ossinsight:trending:past_24_hours",
    )
    repo_b = _candidate(
        "project:acme/repo-b",
        repo_full_name="acme/repo-b",
        raw_signals={"trending_item": {"repo_name": "acme/repo-b"}},
        source_query="github-trending:daily",
    )

    enrichment = enrich_radar_context(
        candidates=[repo_a, repo_b],
        tech_candidates=[],
        builder_signals=[],
    )

    assert enrichment.maintainer_items
    assert enrichment.maintainer_items[0]["title"].startswith("acme：2 个仓库同时冒头")


def test_enrich_radar_context_does_not_treat_x_status_url_as_repo_ref():
    repo = _candidate(
        "project:owner/repo",
        repo_full_name="owner/repo",
        raw_signals={"trending_item": {"repo_name": "owner/repo"}},
        source_query="github-trending:daily",
    )
    signal = BuilderSignal(
        source="x",
        section="x",
        title="Swyx",
        url="https://x.com/swyx/status/2046330825265086712",
        creator="Swyx",
        summary="Talking about agent shells today.",
        score=42,
        published_at="2026-04-10T00:00:00Z",
    )

    enrichment = enrich_radar_context(
        candidates=[repo],
        tech_candidates=[],
        builder_signals=[signal],
    )

    assert enrichment.builder_matches[signal.url]["matched_repos"] == []


def test_enrich_radar_context_does_not_treat_external_blog_url_as_repo_ref():
    repo = _candidate(
        "project:owner/repo",
        repo_full_name="owner/repo",
        raw_signals={"trending_item": {"repo_name": "owner/repo"}},
        source_query="github-trending:daily",
    )
    signal = BuilderSignal(
        source="blog",
        section="blog",
        title="Claude launch notes",
        url="https://claude.com/blog/claude-code-best-practices",
        creator="Claude",
        summary="Launch notes for a new release.",
        score=0,
        published_at="2026-04-10T00:00:00Z",
    )

    enrichment = enrich_radar_context(
        candidates=[repo],
        tech_candidates=[],
        builder_signals=[signal],
    )

    assert enrichment.builder_matches[signal.url]["matched_repos"] == []


def test_enrich_radar_context_still_matches_repo_mentions_inside_builder_copy():
    repo = _candidate(
        "project:owner/repo",
        repo_full_name="owner/repo",
        raw_signals={"trending_item": {"repo_name": "owner/repo"}},
        source_query="github-trending:daily",
    )
    signal = BuilderSignal(
        source="x",
        section="x",
        title="OpenAI",
        url="https://x.com/openai/status/1",
        creator="OpenAI",
        summary="We are shipping owner/repo into production this week.",
        score=128,
        published_at="2026-04-10T00:00:00Z",
    )

    enrichment = enrich_radar_context(
        candidates=[repo],
        tech_candidates=[],
        builder_signals=[signal],
    )

    assert enrichment.builder_matches[signal.url]["matched_repos"] == ["owner/repo"]


def test_enrich_radar_context_skips_low_signal_maintainer_names():
    repo_a = _candidate(
        "project:sponsors/repo-a",
        repo_full_name="sponsors/repo-a",
        raw_signals={"ossinsight_item": {"repo_name": "sponsors/repo-a"}},
        source_query="ossinsight:trending:past_24_hours",
    )
    repo_b = _candidate(
        "project:sponsors/repo-b",
        repo_full_name="sponsors/repo-b",
        raw_signals={"trending_item": {"repo_name": "sponsors/repo-b"}},
        source_query="github-trending:daily",
    )

    enrichment = enrich_radar_context(
        candidates=[repo_a, repo_b],
        tech_candidates=[],
        builder_signals=[],
    )

    assert enrichment.maintainer_items == []
