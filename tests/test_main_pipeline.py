from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from github_daily_radar import main as main_module
from github_daily_radar.config import Settings
from github_daily_radar.models import Candidate, CandidateMetrics
from github_daily_radar.main import product_today, run_pipeline, should_publish, should_update_state


class _GoodCollector:
    name = "repos"

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
    name = "discussions"

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
    name = "issues_prs"

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


class _OtherRepoDiscussionCollector:
    name = "discussions"

    def __init__(self, *args, **kwargs) -> None:
        pass

    def collect(self):
        return [
            Candidate(
                candidate_id="discussion:other",
                kind="discussion",
                source_query="proposal",
                title="Other RFC",
                url="https://github.com/other/repo/discussions/1",
                repo_full_name="other/repo",
                author="other",
                created_at="2026-04-01T00:00:00Z",
                updated_at="2026-04-02T00:00:00Z",
                body_excerpt="discussion",
                topics=[],
                labels=[],
                metrics=CandidateMetrics(comments=10),
                raw_signals={},
                rule_scores={},
                dedupe_key="other-repo-discussion",
            )
        ]


class _GoodSkillCollector:
    name = "skills"

    def __init__(self, *args, **kwargs) -> None:
        pass

    def collect(self):
        return [
            Candidate(
                candidate_id="skill:owner/skill",
                kind="skill",
                source_query="filename:SKILL.md path:skills",
                title="owner/skill",
                url="https://github.com/owner/skill",
                repo_full_name="owner/skill",
                author="owner",
                created_at="2026-04-01T00:00:00Z",
                updated_at="2026-04-02T00:00:00Z",
                body_excerpt="skill",
                topics=["agent"],
                labels=[],
                metrics=CandidateMetrics(stars=500, forks=40),
                raw_signals={},
                rule_scores={},
                dedupe_key="owner/skill",
            )
        ]


class _HotCooldownSkillCollector:
    name = "skills"

    def __init__(self, *args, **kwargs) -> None:
        pass

    def collect(self):
        return [
            Candidate(
                candidate_id="skill:owner/skill",
                kind="skill",
                source_query="filename:SKILL.md path:skills",
                title="owner/skill",
                url="https://github.com/owner/skill",
                repo_full_name="owner/skill",
                author="owner",
                created_at="2026-04-01T00:00:00Z",
                updated_at="2026-04-16T00:00:00Z",
                body_excerpt="skill",
                topics=["agent"],
                labels=[],
                metrics=CandidateMetrics(stars=2600, forks=40, star_growth_7d=1400),
                raw_signals={},
                rule_scores={},
                dedupe_key="owner/skill",
            )
        ]


class _BadCollector:
    name = "skills"

    def __init__(self, *args, **kwargs) -> None:
        pass

    def collect(self):
        raise RuntimeError("boom")


class _GoodOSSInsightCollector:
    name = "ossinsight"

    def __init__(self, *args, **kwargs) -> None:
        pass

    def collect(self):
        return [
            Candidate(
                candidate_id="project:owner/trend",
                kind="project",
                source_query="ossinsight:trending:past_24_hours",
                title="owner/trend",
                url="https://github.com/owner/trend",
                repo_full_name="owner/trend",
                author="owner",
                created_at="2026-04-01T00:00:00Z",
                updated_at="2026-04-02T00:00:00Z",
                body_excerpt="trend",
                topics=["Artificial Intelligence"],
                labels=[],
                metrics=CandidateMetrics(stars=120, forks=10, reactions=180, star_growth_7d=120),
                raw_signals={},
                rule_scores={},
                dedupe_key="owner/trend",
            )
        ]


class _ManyProjectCollector:
    name = "repos"

    def __init__(self, *args, **kwargs) -> None:
        pass

    def collect(self):
        candidates = []
        for index in range(12):
            candidates.append(
                Candidate(
                    candidate_id=f"repo:owner/repo-{index}",
                    kind="project",
                    source_query="topic:agent",
                    title=f"owner/repo-{index}",
                    url=f"https://github.com/owner/repo-{index}",
                    repo_full_name=f"owner/repo-{index}",
                    author="owner",
                    created_at="2026-04-01T00:00:00Z",
                    updated_at="2026-04-02T00:00:00Z",
                    body_excerpt=f"repo {index}",
                    topics=["agent"],
                    labels=[],
                    metrics=CandidateMetrics(stars=100 - index),
                    raw_signals={},
                    rule_scores={},
                    dedupe_key=f"owner/repo-{index}",
                )
            )
        return candidates


class _EmptyCollector:
    name = "empty"

    def __init__(self, *args, **kwargs) -> None:
        pass

    def collect(self):
        return []


class _FakeLLM:
    def __init__(self, *args, **kwargs) -> None:
        _FakeLLM.init_kwargs = kwargs

    def rank_and_summarize(self, candidates):
        _FakeLLM.last_candidates = candidates
        return [
            {
                "kind": "project",
                "title": "owner/name",
                "url": "https://github.com/owner/name",
                "trait": "围绕终端式 AI 编程工作流",
                "capability": "把复杂编码任务拆成可执行命令",
                "necessity": "适合想把 AI 编程沉入日常开发的人",
                "why_now": "今天有进展",
            }
        ]


@pytest.fixture(autouse=True)
def _stub_external_brief_sources(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "BuzzingCollector",
        lambda *args, **kwargs: type("Buzzing", (), {"collect": lambda self: []})(),
    )
    monkeypatch.setattr(
        main_module,
        "fetch_feeds",
        lambda: {
            "x": [],
            "podcasts": [],
            "blogs": [],
            "stats": {"xBuilders": 0, "totalTweets": 0, "podcastEpisodes": 0, "blogPosts": 0},
            "errors": None,
        },
    )


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

    def fake_build_digest_card(*, items, secondary_items=None, tech_items=None, builder_sections=None, surge_items=None, metadata=None, today=None, project_first=True):
        captured["items"] = items
        captured["metadata"] = metadata or {}
        captured["today"] = today
        captured["project_first"] = project_first
        return {"msg_type": "interactive", "card": {"header": {"title": {"content": "test"}}}}

    monkeypatch.setattr(main_module, "TrendingCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "OSSInsightCollector", _GoodOSSInsightCollector)
    monkeypatch.setattr(main_module, "RepoCollector", _GoodCollector)
    monkeypatch.setattr(main_module, "SkillCollector", _BadCollector)
    monkeypatch.setattr(main_module, "DiscussionCollector", _GoodDiscussionCollector)
    monkeypatch.setattr(main_module, "IssuesPrsCollector", _GoodIssuesCollector)
    monkeypatch.setattr(main_module, "EditorialLLM", _FakeLLM)
    monkeypatch.setattr(main_module, "build_digest_card", fake_build_digest_card)
    monkeypatch.setattr(main_module, "send_cards", lambda *args, **kwargs: None)

    settings = Settings.from_env()
    result = run_pipeline(settings=settings)

    assert result["count"] == 4
    assert _FakeLLM.last_candidates[0]["description"] == "trend"
    assert _FakeLLM.last_candidates[0]["topics"] == ["Artificial Intelligence"]
    assert _FakeLLM.last_candidates[0]["labels"] == []
    assert _FakeLLM.last_candidates[0]["signals"]["star_growth_7d"] == 120
    assert _FakeLLM.last_candidates[0]["title"] == "owner/trend"
    assert _FakeLLM.last_candidates[1]["title"] == "owner/name"
    assert _FakeLLM.last_candidates[2]["title"] == "Proposal"
    assert _FakeLLM.last_candidates[3]["title"] == "RFC"
    assert _FakeLLM.init_kwargs["fallback_models"] == ["kimi-k2.5"]
    # 验证 editorial 画像被正确合并
    assert any(
        item["title"] == "owner/name"
        and "特点：" in item["summary"]
        and "核心能力：" in item["summary"]
        and "引入必要性：" in item["summary"]
        for item in captured["items"]
    )
    assert captured["metadata"]["item_count"] == 2
    assert "collector_stats" not in captured["metadata"]
    assert "filtered_kind_counts" not in captured["metadata"]
    assert "published_kind_counts" not in captured["metadata"]

    history = json.loads(Path("artifacts/state/history.json").read_text(encoding="utf-8"))
    assert history["candidate_index"]["project:owner/trend"]["last_seen_metrics"]["stars"] == 120
    assert history["candidate_index"]["project:owner/trend"]["last_published_metrics"]["stars"] == 120
    assert history["run_summaries"][0]["candidate_count"] == 4
    assert history["run_summaries"][0]["collector_stats"]["ossinsight"]["count"] == 1
    assert history["run_summaries"][0]["collector_stats"]["repos"]["count"] == 1
    assert history["run_summaries"][0]["collector_stats"]["skills"]["error"] == "boom"


def test_run_pipeline_respects_report_limit(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("QWEN_API_KEY", "qwen_test")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")
    monkeypatch.setenv("REPORT_LIMIT", "2")

    captured = {}

    def fake_build_digest_card(*, items, secondary_items=None, tech_items=None, builder_sections=None, surge_items=None, metadata=None, today=None, project_first=True):
        captured["items"] = items
        captured["metadata"] = metadata or {}
        captured["project_first"] = project_first
        return {"msg_type": "interactive", "card": {"header": {"title": {"content": "test"}}}}

    monkeypatch.setattr(main_module, "TrendingCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "OSSInsightCollector", _GoodOSSInsightCollector)
    monkeypatch.setattr(main_module, "RepoCollector", _GoodCollector)
    monkeypatch.setattr(main_module, "SkillCollector", _BadCollector)
    monkeypatch.setattr(main_module, "DiscussionCollector", _OtherRepoDiscussionCollector)
    monkeypatch.setattr(main_module, "IssuesPrsCollector", _GoodIssuesCollector)
    monkeypatch.setattr(main_module, "EditorialLLM", _FakeLLM)
    monkeypatch.setattr(main_module, "build_digest_card", fake_build_digest_card)
    monkeypatch.setattr(main_module, "send_cards", lambda *args, **kwargs: None)

    settings = Settings.from_env()
    result = run_pipeline(settings=settings)

    assert result["count"] == 4
    assert captured["metadata"]["item_count"] == 2
    history = json.loads(Path("artifacts/state/history.json").read_text(encoding="utf-8"))
    assert history["run_summaries"][0]["selected_count"] == 2


def test_run_pipeline_single_version_selects_all(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("QWEN_API_KEY", "qwen_test")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")

    captured = {}

    def fake_build_digest_card(*, items, secondary_items=None, tech_items=None, builder_sections=None, surge_items=None, metadata=None, today=None, project_first=True):
        captured["items"] = items
        captured["project_first"] = project_first
        return {"msg_type": "interactive", "card": {"header": {"title": {"content": "test"}}}}

    monkeypatch.setattr(main_module, "TrendingCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "OSSInsightCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "RepoCollector", _ManyProjectCollector)
    monkeypatch.setattr(main_module, "SkillCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "DiscussionCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "IssuesPrsCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "EditorialLLM", _FakeLLM)
    monkeypatch.setattr(main_module, "build_digest_card", fake_build_digest_card)
    monkeypatch.setattr(main_module, "send_cards", lambda *args, **kwargs: None)

    settings = Settings.from_env()
    result = run_pipeline(settings=settings)

    assert result["count"] == 12
    # 单版输出：所有 12 条进入一个列表（limit=20, 12<20）
    assert len(captured["items"]) == 12


def test_run_pipeline_single_card_is_project_first(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("QWEN_API_KEY", "qwen_test")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")

    captured = {}

    def fake_build_digest_card(*, items, secondary_items=None, tech_items=None, builder_sections=None, surge_items=None, metadata=None, today=None, project_first=True):
        captured["items"] = items
        captured["metadata"] = metadata or {}
        captured["project_first"] = project_first
        return {"msg_type": "interactive", "card": {"header": {"title": {"content": "test"}}}}

    monkeypatch.setattr(main_module, "TrendingCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "OSSInsightCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "RepoCollector", _GoodCollector)
    monkeypatch.setattr(main_module, "SkillCollector", _GoodSkillCollector)
    monkeypatch.setattr(main_module, "DiscussionCollector", _OtherRepoDiscussionCollector)
    monkeypatch.setattr(main_module, "IssuesPrsCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "EditorialLLM", _FakeLLM)
    monkeypatch.setattr(main_module, "build_digest_card", fake_build_digest_card)
    monkeypatch.setattr(main_module, "send_cards", lambda *args, **kwargs: None)

    settings = Settings.from_env()
    run_pipeline(settings=settings)

    assert [item["kind"] for item in captured["items"]] == ["project", "skill", "discussion"]
    assert [item["title"] for item in captured["items"]] == ["owner/name", "owner/skill", "Other RFC"]
    assert captured["project_first"] is True


def test_run_pipeline_can_disable_project_first(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("QWEN_API_KEY", "qwen_test")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")

    captured = {}

    def fake_build_digest_card(*, items, secondary_items=None, tech_items=None, builder_sections=None, surge_items=None, metadata=None, today=None, project_first=True):
        captured["items"] = items
        captured["project_first"] = project_first
        return {"msg_type": "interactive", "card": {"header": {"title": {"content": "test"}}}}

    monkeypatch.setattr(main_module, "TrendingCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "OSSInsightCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "RepoCollector", _GoodCollector)
    monkeypatch.setattr(main_module, "SkillCollector", _GoodSkillCollector)
    monkeypatch.setattr(main_module, "DiscussionCollector", _OtherRepoDiscussionCollector)
    monkeypatch.setattr(main_module, "IssuesPrsCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "EditorialLLM", _FakeLLM)
    monkeypatch.setattr(main_module, "build_digest_card", fake_build_digest_card)
    monkeypatch.setattr(main_module, "send_cards", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        main_module,
        "load_output_daily_item_count_config",
        lambda: {"min": 3, "max": 5, "project_first": False},
    )

    settings = Settings.from_env()
    run_pipeline(settings=settings)

    assert captured["project_first"] is False
    assert [item["kind"] for item in captured["items"]] == ["skill", "discussion", "project"]


def test_run_pipeline_uses_configured_daily_item_count(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("QWEN_API_KEY", "qwen_test")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")

    captured = {}

    def fake_build_digest_card(*, items, secondary_items=None, tech_items=None, builder_sections=None, surge_items=None, metadata=None, today=None, project_first=True):
        captured["items"] = items
        captured["metadata"] = metadata or {}
        captured["project_first"] = project_first
        return {"msg_type": "interactive", "card": {"header": {"title": {"content": "test"}}}}

    monkeypatch.setattr(main_module, "TrendingCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "OSSInsightCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "RepoCollector", _ManyProjectCollector)
    monkeypatch.setattr(main_module, "SkillCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "DiscussionCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "IssuesPrsCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "EditorialLLM", _FakeLLM)
    monkeypatch.setattr(main_module, "build_digest_card", fake_build_digest_card)
    monkeypatch.setattr(main_module, "send_cards", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        main_module,
        "load_output_daily_item_count_config",
        lambda: {"min": 3, "max": 5, "project_first": True},
    )
    monkeypatch.setattr(main_module, "load_skill_per_repo_cap", lambda: 1)

    settings = Settings.from_env()
    result = run_pipeline(settings=settings)

    assert result["count"] == 12
    assert len(captured["items"]) == 5
    assert captured["metadata"]["item_count"] == 5


def test_run_pipeline_applies_theme_cooldown_from_previous_day(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("QWEN_API_KEY", "qwen_test")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")

    history_dir = Path("artifacts/state")
    history_dir.mkdir(parents=True, exist_ok=True)
    (history_dir / "history.json").write_text(
        json.dumps(
            {
                "published": [],
                "candidate_index": {},
                "run_summaries": [
                    {
                        "date": "2026-04-01",
                        "top_themes": ["claude_code", "mcp"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    captured = {}

    def fake_select_top_items(items, **kwargs):
        captured["blocked_themes"] = kwargs.get("blocked_themes")
        return items[:1]

    def fake_build_digest_card(*, items, secondary_items=None, tech_items=None, builder_sections=None, surge_items=None, metadata=None, today=None, project_first=True):
        captured["items"] = items
        return {"msg_type": "interactive", "card": {"header": {"title": {"content": "test"}}}}

    monkeypatch.setattr(main_module, "TrendingCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "OSSInsightCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "RepoCollector", _GoodCollector)
    monkeypatch.setattr(main_module, "SkillCollector", _GoodSkillCollector)
    monkeypatch.setattr(main_module, "DiscussionCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "IssuesPrsCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "EditorialLLM", _FakeLLM)
    monkeypatch.setattr(main_module, "select_top_items", fake_select_top_items)
    monkeypatch.setattr(main_module, "build_digest_card", fake_build_digest_card)
    monkeypatch.setattr(main_module, "send_cards", lambda *args, **kwargs: None)

    settings = Settings.from_env()
    run_pipeline(settings=settings)

    assert captured["blocked_themes"] == {"claude_code", "mcp"}


def test_build_recent_skill_star_baselines_ignores_unreliable_ossinsight_records(tmp_path: Path):
    state_dir = tmp_path / "artifacts" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "history.json").write_text(
        json.dumps({"published": [], "candidate_index": {}, "run_summaries": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (state_dir / "history.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "candidate_id": "project:obra/superpowers",
                        "date": "2026-04-15",
                        "event": "seen",
                        "source_query": "ossinsight:collection:foo",
                        "metrics": {"stars": 2260},
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "candidate_id": "skill:refly-ai/refly",
                        "date": "2026-04-15",
                        "event": "seen",
                        "source_query": "claude skills agent prompt in:name,description",
                        "metrics": {"stars": 7216},
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    baselines = main_module._build_recent_skill_star_baselines(
        main_module.StateStore(base_dir=state_dir),
        today=datetime(2026, 4, 16, tzinfo=timezone.utc).date(),
    )

    assert baselines == {"refly-ai/refly": 7216}


def test_run_pipeline_allows_super_growth_skill_to_bypass_global_cooldown(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("QWEN_API_KEY", "qwen_test")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")

    history_dir = Path("artifacts/state")
    history_dir.mkdir(parents=True, exist_ok=True)
    (history_dir / "history.json").write_text(
        json.dumps(
            {
                "published": [
                    {
                        "candidate_id": "skill:owner/skill",
                        "date": "2026-04-15",
                        "kind": "skill",
                        "title": "owner/skill",
                        "metrics": {"stars": 1200},
                    }
                ],
                "candidate_index": {
                    "skill:owner/skill": {
                        "candidate_id": "skill:owner/skill",
                        "last_published_at": "2026-04-15",
                        "last_seen_at": "2026-04-15",
                        "last_seen_metrics": {"stars": 1200},
                    }
                },
                "run_summaries": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    captured = {}

    def fake_build_digest_card(*, items, secondary_items=None, tech_items=None, builder_sections=None, surge_items=None, metadata=None, today=None, project_first=True):
        captured["items"] = items
        return {"msg_type": "interactive", "card": {"header": {"title": {"content": "test"}}}}

    monkeypatch.setattr(main_module, "TrendingCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "OSSInsightCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "RepoCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "SkillCollector", _HotCooldownSkillCollector)
    monkeypatch.setattr(main_module, "DiscussionCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "IssuesPrsCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "EditorialLLM", _FakeLLM)
    monkeypatch.setattr(main_module, "build_digest_card", fake_build_digest_card)
    monkeypatch.setattr(main_module, "send_cards", lambda *args, **kwargs: None)

    settings = Settings.from_env()
    result = run_pipeline(settings=settings)

    assert result["count"] == 1
    assert [item["title"] for item in captured["items"]] == ["owner/skill"]


def test_run_pipeline_builds_single_daily_brief_with_tech_and_builder_tracks(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("QWEN_API_KEY", "qwen_test")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")

    captured = {}

    def fake_build_digest_card(*, items, tech_items=None, builder_sections=None, surge_items=None, metadata=None, today=None, project_first=True):
        captured["items"] = items
        captured["tech_items"] = tech_items
        captured["builder_sections"] = builder_sections
        return {"msg_type": "interactive", "card": {"header": {"title": {"content": "test"}}}}

    monkeypatch.setattr(main_module, "TrendingCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "OSSInsightCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "RepoCollector", _GoodCollector)
    monkeypatch.setattr(main_module, "SkillCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "DiscussionCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "IssuesPrsCollector", _EmptyCollector)
    monkeypatch.setattr(main_module, "BuzzingCollector", lambda *args, **kwargs: type("Buzzing", (), {"collect": lambda self: []})())
    monkeypatch.setattr(
        main_module,
        "fetch_feeds",
        lambda: {
            "x": [
                {
                    "source": "x",
                    "name": "Swyx",
                    "handle": "swyx",
                    "tweets": [{"url": "https://x.com/swyx/status/1", "text": "Builder thread", "likes": 42, "createdAt": "2026-04-16T00:00:00Z"}],
                }
            ],
            "podcasts": [],
            "blogs": [],
            "stats": {"xBuilders": 1, "totalTweets": 1, "podcastEpisodes": 0, "blogPosts": 0},
            "errors": None,
        },
    )
    monkeypatch.setattr(main_module, "EditorialLLM", _FakeLLM)
    monkeypatch.setattr(main_module, "build_digest_card", fake_build_digest_card)
    monkeypatch.setattr(main_module, "send_cards", lambda *args, **kwargs: None)

    settings = Settings.from_env()
    run_pipeline(settings=settings)

    assert captured["items"]
    assert captured["tech_items"] == []
    assert captured["builder_sections"]["x"][0]["title"].startswith("Swyx：")
    assert "围绕" in captured["builder_sections"]["x"][0]["why_now"]
