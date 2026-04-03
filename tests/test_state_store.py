from datetime import date, timedelta
import json
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

    store.record_seen(date(2026, 4, 2), [candidate])
    store.record_published(date(2026, 4, 2), [candidate])
    store.record_run_summary(date(2026, 4, 2), {"candidate_count": 1, "selected_count": 1})
    history = store.read_history()

    assert history["published"][0]["candidate_id"] == "repo:owner/name"
    assert history["candidate_index"]["repo:owner/name"]["last_seen_metrics"]["stars"] == 10
    assert history["candidate_index"]["repo:owner/name"]["last_published_metrics"]["stars"] == 10
    assert history["run_summaries"][0]["candidate_count"] == 1

    history_lines = (tmp_path / "history.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert [json.loads(line)["event"] for line in history_lines] == ["seen", "published", "run_summary"]


def test_cooldown_detection(tmp_path: Path):
    store = StateStore(tmp_path)
    candidate_id = "repo:owner/name"
    run_date = date(2026, 4, 2)

    store._append_history_entry(
        run_date - timedelta(days=1),
        candidate_id,
        metrics={"stars": 1},
        scores={"novelty": 0.4},
        event="published",
    )

    assert store.is_in_cooldown(candidate_id, cooldown_days=14, as_of=run_date) is True
    assert store.is_in_cooldown(candidate_id, cooldown_days=1, as_of=run_date) is False


def test_read_last_run_summary(tmp_path: Path):
    store = StateStore(tmp_path)
    store.record_run_summary(date(2026, 4, 1), {"candidate_count": 1, "top_themes": ["claude_code"]})
    store.record_run_summary(date(2026, 4, 2), {"candidate_count": 2, "top_themes": ["mcp"]})

    summary = store.read_last_run_summary()

    assert summary is not None
    assert summary["candidate_count"] == 2
    assert summary["top_themes"] == ["mcp"]
