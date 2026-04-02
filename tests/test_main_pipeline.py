import os

from github_daily_radar.config import Settings
from github_daily_radar.main import run_pipeline, should_publish, should_update_state


def test_publish_and_state_skip_on_dry_run():
    assert should_publish(dry_run=True) is False
    assert should_update_state(dry_run=True) is False


def test_alert_only_short_circuits_pipeline(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("QWEN_API_KEY", "qwen_test")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")

    settings = Settings.from_env()
    result = run_pipeline(settings=settings, alert_only=True)

    assert result == {"mode": "alert-only"}


def test_alert_only_disables_publish_and_state():
    assert should_publish(dry_run=False, alert_only=True) is False
    assert should_update_state(dry_run=False, alert_only=True) is False
