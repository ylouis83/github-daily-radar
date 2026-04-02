from datetime import datetime, timezone
from pathlib import Path

from github_daily_radar.discovery import (
    build_discussion_queries,
    build_issue_pr_queries,
    build_repo_queries,
    build_skill_queries,
    cycle_queries,
    load_ossinsight_collection_name_keywords,
    load_ossinsight_collection_period,
    load_ossinsight_enabled,
    load_ossinsight_language,
    load_ossinsight_max_collection_ids,
    load_ossinsight_max_trending_items,
    load_ossinsight_trending_periods,
    load_issue_pr_keywords,
    load_radar_config,
    load_seed_orgs,
    load_seed_repos,
    load_skill_code_queries,
    load_skill_repo_queries,
    load_skill_seed_repos,
    load_topics,
    recent_date,
)


def test_recent_date_uses_utc_cutoff():
    instant = datetime(2026, 4, 2, 12, 0, tzinfo=timezone.utc)

    assert recent_date(days=7, now=instant) == "2026-03-26"


def test_build_repo_and_skill_queries_are_dynamic():
    instant = datetime(2026, 4, 2, 12, 0, tzinfo=timezone.utc)

    repo_queries = build_repo_queries(now=instant, days_back=7)
    skill_queries = build_skill_queries(now=instant, days_back=14)

    assert "pushed:>2026-03-26" in repo_queries[0]
    assert "pushed:>2026-03-19" in skill_queries[0]


def test_load_seed_repos_reads_yaml(tmp_path: Path):
    path = tmp_path / "seed_repos.yaml"
    path.write_text("seed_repos:\n  - a/b\n  - c/d\n", encoding="utf-8")

    assert load_seed_repos(path) == ["a/b", "c/d"]


def test_load_skill_matrix_reads_yaml(tmp_path: Path):
    path = tmp_path / "seed_repos.yaml"
    path.write_text(
        """
topics:
  - agent
seed_orgs:
  - openai
skills:
  seed_skill_repos:
    - obra/superpowers
  code_search_queries:
    - filename:SKILL.md
  repo_search_queries:
    - cursor rules AI in:name,description
discussion_keywords:
  - proposal
issue_pr_keywords:
  - roadmap
""".strip(),
        encoding="utf-8",
    )

    assert load_topics(path) == ["agent"]
    assert load_seed_orgs(path) == ["openai"]
    assert load_skill_seed_repos(path) == ["obra/superpowers"]
    assert load_skill_code_queries(path) == ["filename:SKILL.md"]
    assert load_skill_repo_queries(path) == ["cursor rules AI in:name,description"]
    assert load_issue_pr_keywords(path) == ["roadmap"]
    assert load_radar_config(path)["topics"] == ["agent"]


def test_load_ossinsight_matrix_reads_yaml(tmp_path: Path):
    path = tmp_path / "seed_repos.yaml"
    path.write_text(
        """
ossinsight:
  enabled: false
  language: Python
  trending_periods:
    - past_24_hours
  collection_period: past_7_days
  collection_name_keywords:
    - ai
  max_trending_items: 12
  max_collection_ids: 2
""".strip(),
        encoding="utf-8",
    )

    assert load_ossinsight_enabled(path) is False
    assert load_ossinsight_language(path) == "Python"
    assert load_ossinsight_trending_periods(path) == ["past_24_hours"]
    assert load_ossinsight_collection_period(path) == "past_7_days"
    assert load_ossinsight_collection_name_keywords(path) == ["ai"]
    assert load_ossinsight_max_trending_items(path) == 12
    assert load_ossinsight_max_collection_ids(path) == 2


def test_seed_repo_queries_are_chunked_and_scoped():
    instant = datetime(2026, 4, 2, 12, 0, tzinfo=timezone.utc)
    seed_repos = ["a/b", "c/d", "e/f", "g/h", "i/j"]

    discussion_queries = build_discussion_queries(seed_repos=seed_repos, now=instant, days_back=14)
    issue_queries = build_issue_pr_queries(seed_repos=seed_repos, now=instant, days_back=14)

    assert len(discussion_queries) == 4
    assert len(issue_queries) == 4
    assert "repo:a/b OR repo:c/d" in discussion_queries[0]
    assert "is:issue" in discussion_queries[0]
    assert "comments:>=5" in discussion_queries[0]
    assert "updated:>2026-03-19" in discussion_queries[0]
    assert "is:open" in issue_queries[0]
    assert "comments:>=3" in issue_queries[0]


def test_cycle_queries_rotates_a_daily_subset():
    queries = ["q1", "q2", "q3", "q4", "q5"]

    assert cycle_queries(queries, limit=2, seed=0) == ["q1", "q2"]
    assert cycle_queries(queries, limit=2, seed=1) == ["q2", "q3"]
    assert cycle_queries(queries, limit=2, seed=4) == ["q5", "q1"]


def test_query_builders_stay_within_boolean_operator_limits():
    instant = datetime(2026, 4, 2, 12, 0, tzinfo=timezone.utc)
    seed_repos = [
        "modelcontextprotocol/specification",
        "modelcontextprotocol/servers",
        "anthropics/claude-code",
        "cline/cline",
        "All-Hands-AI/OpenHands",
        "paul-gauthier/aider",
        "langchain-ai/langgraph",
    ]

    repo_queries = build_repo_queries(now=instant, days_back=7)
    discussion_queries = build_discussion_queries(seed_repos=seed_repos, now=instant, days_back=14)
    issue_queries = build_issue_pr_queries(seed_repos=seed_repos, now=instant, days_back=14)

    assert all(query.count(" OR ") == 0 for query in repo_queries)
    assert all(query.count(" OR ") <= 5 for query in discussion_queries)
    assert all(query.count(" OR ") <= 5 for query in issue_queries)
