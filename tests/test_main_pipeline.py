from datetime import datetime, timezone
import json
from pathlib import Path

from github_daily_radar import main as main_module
from github_daily_radar.config import Settings
from github_daily_radar.models import Candidate, CandidateMetrics
from github_daily_radar.main import product_today, run_pipeline, should_publish, should_update_state


class _GoodCollector:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def collect(self):
        return [
            Candidate(
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
        ]


class _GoodDiscussionCollector:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def collect(self):
        return [
            Candidate(
                candidate_id="discussion:1",
                kind="discussion",
                source_query="proposal",
                title="RFC",
                url="https://github.com/owner/name/discussions/1",
                repo_full_name="owner/name",
                author="owner",
                created_at="2026-04-01T00:00:00Z",
                updated_at="2026-04-02T00:00:00Z",
                body_excerpt="discussion",
                topics=[],
                labels=[],
                metrics=CandidateMetrics(comments=10),
                raw_signals={},
                rule_scores={},
                dedupe_key="1",
            )
        ]


class _GoodIssuesCollector:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def collect(self):
        return [
            Candidate(
                candidate_id="issue:2",
                kind="issue",
                source_query="proposal",
                title="Proposal",
                url="https://github.com/owner/name/issues/2",
                repo_full_name="owner/name",
                author="owner",
                created_at="2026-04-01T00:00:00Z",
                updated_at="2026-04-02T00:00:00Z",
                body_excerpt="issue",
                topics=[],
                labels=[],
                metrics=CandidateMetrics(comments=12),
                raw_signals={},
                rule_scores={},
                dedupe_key="2",
            )
        ]


class _BadCollector:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def collect(self):
        raise RuntimeError("boom")


class _FakeLLM:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def rank_and_summarize(self, candidates):
        return [
            {
                "kind": "project",
                "title": "owner/name",
                "url": "https://github.com/owner/name",
                "summary": "中文摘要",
            }
        ]


def test_product_today_uses_product_timezone():
    instant = datetime(2026, 4, 2, 16, 30, tzinfo=timezone.utc)

    assert product_today(timezone_name="Asia/Shanghai", now=instant).isoformat() == "2026-04-03"


def test_publish_and_state_skip_on_dry_run():
    assert should_publish(dry_run=True) is False
    assert should_update_state(dry_run=True) is False


def test_alert_only_short_circuits_pipeline(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("QWEN_API_KEY", "qwen_test")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")
    monkeypatch.setattr(main_module, "send_cards", lambda *args, **kwargs: None)

    settings = Settings.from_env()
    result = run_pipeline(settings=settings, alert_only=True)

    assert result == {"mode": "alert-only"}


def test_alert_only_disables_publish_and_state():
    assert should_publish(dry_run=False, alert_only=True) is False
    assert should_update_state(dry_run=False, alert_only=True) is False


def test_alert_only_sends_feishu_alert(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("QWEN_API_KEY", "qwen_test")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")

    captured = {}

    def fake_send_cards(*, webhook_url, cards):
        captured["webhook_url"] = webhook_url
        captured["cards"] = cards

    monkeypatch.setattr(main_module, "send_cards", fake_send_cards)

    settings = Settings.from_env()
    result = run_pipeline(settings=settings, alert_only=True)

    assert result == {"mode": "alert-only"}
    assert captured["webhook_url"] == "https://example.com/hook"
    assert len(captured["cards"]) == 1
    assert "alert" in captured["cards"][0]["card"]["header"]["title"]["content"].lower()


def test_run_pipeline_uses_editorial_summaries_and_continues_on_collector_failure(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("QWEN_API_KEY", "qwen_test")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")

    captured = {}

    def fake_build_cards(*, title, sections, metadata=None, max_lines=20):
        captured["title"] = title
        captured["sections"] = sections
        captured["metadata"] = metadata or {}
        return [{"msg_type": "interactive", "card": {"header": {"title": {"content": title}}}}]

    monkeypatch.setattr(main_module, "RepoCollector", _GoodCollector)
    monkeypatch.setattr(main_module, "SkillCollector", _BadCollector)
    monkeypatch.setattr(main_module, "DiscussionCollector", _GoodDiscussionCollector)
    monkeypatch.setattr(main_module, "IssuesPrsCollector", _GoodIssuesCollector)
    monkeypatch.setattr(main_module, "EditorialLLM", _FakeLLM)
    monkeypatch.setattr(main_module, "build_cards", fake_build_cards)
    monkeypatch.setattr(main_module, "send_cards", lambda *args, **kwargs: None)

    settings = Settings.from_env()
    result = run_pipeline(settings=settings)

    assert result["count"] == 3
    assert captured["sections"][0]["items"][0]["summary"] == "中文摘要"
    assert captured["metadata"]["collector_errors"] == 1

    history = json.loads(Path("artifacts/state/history.json").read_text(encoding="utf-8"))
    assert history["candidate_index"]["repo:owner/name"]["last_seen_metrics"]["stars"] == 10
    assert history["candidate_index"]["repo:owner/name"]["last_published_metrics"]["stars"] == 10
    assert history["run_summaries"][0]["candidate_count"] == 3
