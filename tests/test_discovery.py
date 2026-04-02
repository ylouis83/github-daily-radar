from datetime import datetime, timezone
from pathlib import Path

from github_daily_radar.discovery import (
    build_discussion_queries,
    build_issue_pr_queries,
    build_repo_queries,
    build_skill_queries,
    load_seed_repos,
    recent_date,
)


def test_recent_date_uses_utc_cutoff():
    instant = datetime(2026, 4, 2, 12, 0, tzinfo=timezone.utc)

    assert recent_date(days=7, now=instant) == "2026-03-26"


def test_build_repo_and_skill_queries_are_dynamic():
    instant = datetime(2026, 4, 2, 12, 0, tzinfo=timezone.utc)

    repo_queries = build_repo_queries(now=instant)
    skill_queries = build_skill_queries(now=instant)

    assert "pushed:>2026-03-26" in repo_queries[0]
    assert "pushed:>2026-03-19" in skill_queries[0]


def test_load_seed_repos_reads_yaml(tmp_path: Path):
    path = tmp_path / "seed_repos.yaml"
    path.write_text("seed_repos:\n  - a/b\n  - c/d\n", encoding="utf-8")

    assert load_seed_repos(path) == ["a/b", "c/d"]


def test_seed_repo_queries_are_chunked_and_scoped():
    instant = datetime(2026, 4, 2, 12, 0, tzinfo=timezone.utc)
    seed_repos = ["a/b", "c/d", "e/f", "g/h", "i/j"]

    discussion_queries = build_discussion_queries(seed_repos=seed_repos, now=instant, chunk_size=2)
    issue_queries = build_issue_pr_queries(seed_repos=seed_repos, now=instant, chunk_size=2)

    assert len(discussion_queries) == 3
    assert len(issue_queries) == 3
    assert "repo:a/b OR repo:c/d" in discussion_queries[0]
    assert "is:issue" in discussion_queries[0]
    assert "updated:>2026-03-19" in discussion_queries[0]
    assert "is:pr" in issue_queries[0]
