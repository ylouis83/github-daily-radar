from github_daily_radar.config import Settings


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("QWEN_API_KEY", "qwen_test")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")

    settings = Settings.from_env()

    assert settings.timezone == "Asia/Shanghai"
    assert settings.default_model == "qwen3.5-plus"
    assert settings.dry_run is False
    assert settings.llm_max_candidates == 24
    assert settings.search_requests_per_minute == 25
    assert settings.code_search_requests_per_minute == 10
    assert settings.daily_schedule_hour_utc == 1
    assert settings.report_limit == 0


def test_dry_run_flag(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("QWEN_API_KEY", "qwen_test")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")
    monkeypatch.setenv("DRY_RUN", "true")

    settings = Settings.from_env()

    assert settings.dry_run is True


def test_pat_override(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_default")
    monkeypatch.setenv("GITHUB_PAT", "ghp_override")
    monkeypatch.setenv("QWEN_API_KEY", "qwen_test")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")

    settings = Settings.from_env()

    assert settings.github_auth_token == "ghp_override"


def test_report_limit_override(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("QWEN_API_KEY", "qwen_test")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")
    monkeypatch.setenv("REPORT_LIMIT", "2")

    settings = Settings.from_env()

    assert settings.report_limit == 2
