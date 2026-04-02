from pathlib import Path

from github_daily_radar.state.store import StateStore


def test_bootstrap_detects_missing_history(tmp_path: Path):
    store = StateStore(tmp_path)

    assert store.detect_bootstrap() is True


def test_bootstrap_false_when_history_present(tmp_path: Path):
    store = StateStore(tmp_path)
    store.write_daily_state("2026-04-02", {"count": 0})

    assert store.detect_bootstrap() is False
