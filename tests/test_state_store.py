from datetime import date, timedelta
from pathlib import Path

from github_daily_radar.models import Candidate, CandidateMetrics
from github_daily_radar.state.store import StateStore


def test_state_store_records_and_reads_history(tmp_path: Path):
    store = StateStore(tmp_path)
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
        body_excerpt="repo",
        topics=["agent"],
        labels=[],
        metrics=CandidateMetrics(stars=10),
        raw_signals={},
        rule_scores={},
        dedupe_key="owner/name",
    )

    store.record_published(date(2026, 4, 2), [candidate])
    history = store.read_history()

    assert history["published"][0]["candidate_id"] == "repo:owner/name"


def test_cooldown_detection(tmp_path: Path):
    store = StateStore(tmp_path)
    candidate_id = "repo:owner/name"
    run_date = date(2026, 4, 2)

    store.record_published(run_date - timedelta(days=1), [])
    store.record_published(run_date, [])
    store.record_published(run_date - timedelta(days=3), [])
    store.record_published(run_date - timedelta(days=2), [])

    store._append_history_entry(run_date - timedelta(days=1), candidate_id)

    assert store.is_in_cooldown(candidate_id, cooldown_days=14, as_of=run_date) is True
    assert store.is_in_cooldown(candidate_id, cooldown_days=1, as_of=run_date) is False
