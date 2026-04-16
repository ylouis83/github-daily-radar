from pathlib import Path


def test_workflow_contains_dry_run_and_concurrency():
    workflow = Path(".github/workflows/daily-radar.yml").read_text(encoding="utf-8")
    assert "dry_run:" in workflow
    assert "concurrency:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "failure()" in workflow
    assert "bash scripts/sync_state_branch.sh" in workflow


def test_state_sync_script_uses_worktree():
    script = Path("scripts/sync_state_branch.sh").read_text(encoding="utf-8")
    assert "git worktree add" in script


def test_workflow_no_longer_runs_ai_builders_as_separate_job():
    workflow = Path(".github/workflows/daily-radar.yml").read_text(encoding="utf-8")
    assert "ai-builders:" not in workflow


def test_preview_workflow_dispatch_exists():
    workflow = Path(".github/workflows/preview-card.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "uv run python -m github_daily_radar.preview" in workflow
    assert "FEISHU_WEBHOOK_URL" in workflow


def test_daily_radar_workflow_supports_preview_card_mode():
    workflow = Path(".github/workflows/daily-radar.yml").read_text(encoding="utf-8")
    assert "preview_card:" in workflow
    assert "uv run python -m github_daily_radar.preview" in workflow
