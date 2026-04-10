# GitHub Daily Radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a GitHub Actions based daily radar that discovers high-signal GitHub repositories, skills, and idea-heavy GitHub threads, then sends a Chinese Feishu interactive-card digest with dry-run support, bootstrap handling, explicit API budgets, and persistent history in a dedicated `state` branch.

**Architecture:** A typed Python pipeline uses throttled REST search for broad discovery and GraphQL for shortlist enrichment, normalizes all source records into a shared `Candidate` model, scores them with deterministic heuristics, applies an OpenAI-compatible LLM editorial pass with fallback, renders Feishu interactive cards, and persists publish history plus daily artifacts through a separate state worktree.

**Tech Stack:** Python 3.12, `httpx`, `pydantic`, `pydantic-settings`, `pytest`, `respx`, `tenacity`, `PyYAML`, GitHub Actions, Feishu webhook cards, OpenAI-compatible chat completion API with default `codingplan` model override support.

---

### Task 1: Bootstrap the package, configuration, and typed domain models

**Files:**
- Create: `pyproject.toml`
- Create: `src/github_daily_radar/__init__.py`
- Create: `src/github_daily_radar/config.py`
- Create: `src/github_daily_radar/models.py`
- Create: `tests/test_config.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing tests for configuration and `Candidate` typing**

```python
# tests/test_config.py
from github_daily_radar.config import Settings


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("QWEN_API_KEY", "qwen_test")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")

    settings = Settings.from_env()

    assert settings.timezone == "Asia/Shanghai"
    assert settings.default_model == "codingplan"
    assert settings.dry_run is False
    assert settings.llm_max_candidates == 24
    assert settings.search_requests_per_minute == 25
    assert settings.daily_schedule_hour_utc == 1


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
```

```python
# tests/test_models.py
from github_daily_radar.models import Candidate, CandidateMetrics


def test_candidate_keeps_required_fields():
    candidate = Candidate(
        candidate_id="repo:owner/name",
        kind="project",
        source_query="topic:agent created:>2026-03-26",
        title="owner/name",
        url="https://github.com/owner/name",
        repo_full_name="owner/name",
        author="owner",
        created_at="2026-04-01T00:00:00Z",
        updated_at="2026-04-02T00:00:00Z",
        body_excerpt="A useful repo",
        topics=["agent"],
        labels=[],
        metrics=CandidateMetrics(stars=120, forks=8, comments=0, reactions=0, star_growth_7d=30),
        raw_signals={"source": "search"},
        rule_scores={"novelty": 0.4, "signal": 0.5, "utility": 0.6, "taste": 0.2},
        dedupe_key="owner/name",
    )

    assert candidate.kind == "project"
    assert candidate.metrics.stars == 120
```

- [ ] **Step 2: Run the tests to verify the package is missing**

Run: `python -m pytest tests/test_config.py tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'github_daily_radar'`

- [ ] **Step 3: Create package metadata, settings, and the shared models**

```toml
# pyproject.toml
[project]
name = "github-daily-radar"
version = "0.1.0"
description = "Daily GitHub radar that sends Feishu digests."
requires-python = ">=3.12"
dependencies = [
  "httpx>=0.28.1",
  "pydantic>=2.11.0",
  "pydantic-settings>=2.8.0",
  "PyYAML>=6.0.2",
  "tenacity>=9.0.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3.5",
  "pytest-cov>=6.0.0",
  "respx>=0.22.0",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

```python
# src/github_daily_radar/config.py
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    github_token: str = Field(alias="GITHUB_TOKEN")
    github_pat: str | None = Field(default=None, alias="GITHUB_PAT")
    qwen_api_key: str = Field(alias="QWEN_API_KEY")
    feishu_webhook_url: str = Field(alias="FEISHU_WEBHOOK_URL")
    dry_run: bool = Field(default=False, alias="DRY_RUN")
    timezone: str = Field(default="Asia/Shanghai", alias="TIMEZONE")
    default_model: str = Field(default="codingplan", alias="LLM_MODEL")
    llm_max_candidates: int = Field(default=24, alias="LLM_MAX_CANDIDATES")
    search_requests_per_minute: int = Field(default=25, alias="SEARCH_REQUESTS_PER_MINUTE")
    api_total_budget: int = Field(default=36, alias="API_TOTAL_BUDGET")
    api_search_budget: int = Field(default=18, alias="API_SEARCH_BUDGET")
    api_graphql_budget: int = Field(default=600, alias="API_GRAPHQL_BUDGET")
    cooldown_days: int = Field(default=14, alias="COOLDOWN_DAYS")
    daily_schedule_hour_utc: int = Field(default=1, alias="DAILY_SCHEDULE_HOUR_UTC")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()

    @property
    def github_auth_token(self) -> str:
        return self.github_pat or self.github_token
```

```python
# src/github_daily_radar/models.py
from typing import Literal

from pydantic import BaseModel, Field


class CandidateMetrics(BaseModel):
    stars: int = 0
    forks: int = 0
    comments: int = 0
    reactions: int = 0
    star_growth_7d: int = 0
    previous_star_growth_7d: int = 0
    has_new_release: bool = False
    days_since_previous_release: int | None = None


class Candidate(BaseModel):
    candidate_id: str
    kind: Literal["project", "skill", "discussion", "issue", "pr"]
    source_query: str
    title: str
    url: str
    repo_full_name: str
    author: str
    created_at: str
    updated_at: str
    body_excerpt: str
    topics: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    metrics: CandidateMetrics
    raw_signals: dict = Field(default_factory=dict)
    rule_scores: dict[str, float] = Field(default_factory=dict)
    llm_summary: str | None = None
    llm_reason: str | None = None
    final_score: float = 0.0
    dedupe_key: str


class DailyDigest(BaseModel):
    date_key: str
    timezone: str
    overview: dict
    items: list[Candidate]
```

- [ ] **Step 4: Re-run the tests**

Run: `python -m pytest tests/test_config.py tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit the package bootstrap**

```bash
git add pyproject.toml src/github_daily_radar/__init__.py src/github_daily_radar/config.py src/github_daily_radar/models.py tests/test_config.py tests/test_models.py
git commit -m "feat: bootstrap typed radar package"
```

### Task 2: Implement the GitHub API client and collector base interface

**Files:**
- Create: `src/github_daily_radar/client.py`
- Create: `src/github_daily_radar/collectors/__init__.py`
- Create: `src/github_daily_radar/collectors/base.py`
- Create: `tests/test_client.py`

- [ ] **Step 1: Write the failing tests for API budgets and real HTTP calls**

```python
# tests/test_client.py
import respx
from httpx import Response

from github_daily_radar.client import BudgetTracker, GitHubClient


def test_budget_tracker_consumes_budget():
    tracker = BudgetTracker(total_budget=10, search_budget=2, graphql_budget=5)
    tracker.consume_search()
    tracker.consume_graphql(cost=2)
    assert tracker.search_used == 1
    assert tracker.graphql_used == 2


@respx.mock
def test_search_repositories_hits_rest_api():
    route = respx.get("https://api.github.com/search/repositories").mock(
        return_value=Response(200, json={"items": [{"full_name": "owner/repo"}]})
    )

    client = GitHubClient(
        token="ghs_test",
        budget=BudgetTracker(total_budget=10, search_budget=2, graphql_budget=10),
    )

    payload = client.search_repositories("topic:agent")

    assert route.called is True
    assert payload["items"][0]["full_name"] == "owner/repo"
```

- [ ] **Step 2: Run the tests to verify the client does not exist**

Run: `python -m pytest tests/test_client.py -v`
Expected: FAIL with import errors for `github_daily_radar.client`

- [ ] **Step 3: Implement the client and collector base class**

```python
# src/github_daily_radar/client.py
from dataclasses import dataclass
from threading import Lock
from time import monotonic, sleep

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


@dataclass
class BudgetTracker:
    total_budget: int
    search_budget: int
    graphql_budget: int
    search_used: int = 0
    graphql_used: int = 0

    def consume_search(self) -> None:
        if self.search_used >= self.search_budget:
            raise RuntimeError("search budget exhausted")
        self.search_used += 1

    def consume_graphql(self, cost: int) -> None:
        if self.graphql_used + cost > self.graphql_budget:
            raise RuntimeError("graphql budget exhausted")
        self.graphql_used += cost


class GitHubClient:
    def __init__(self, token: str, budget: BudgetTracker, search_requests_per_minute: int = 25) -> None:
        self._budget = budget
        self._search_lock = Lock()
        self._min_search_interval = 60 / search_requests_per_minute
        self._next_search_at = 0.0
        self._http = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    def _throttle_search(self) -> None:
        with self._search_lock:
            now = monotonic()
            wait_for = self._next_search_at - now
            if wait_for > 0:
                sleep(wait_for)
            self._next_search_at = monotonic() + self._min_search_interval

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), retry=retry_if_exception_type(httpx.HTTPError))
    def search_repositories(self, query: str, per_page: int = 20) -> dict:
        self._budget.consume_search()
        self._throttle_search()
        response = self._http.get("/search/repositories", params={"q": query, "per_page": per_page})
        response.raise_for_status()
        return response.json()

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), retry=retry_if_exception_type(httpx.HTTPError))
    def search_issues(self, query: str, per_page: int = 20) -> dict:
        self._budget.consume_search()
        self._throttle_search()
        response = self._http.get("/search/issues", params={"q": query, "per_page": per_page})
        response.raise_for_status()
        return response.json()

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), retry=retry_if_exception_type(httpx.HTTPError))
    def graphql(self, query: str, variables: dict | None = None, cost: int = 1) -> dict:
        self._budget.consume_graphql(cost=cost)
        response = self._http.post("/graphql", json={"query": query, "variables": variables or {}})
        response.raise_for_status()
        return response.json()
```

```python
# src/github_daily_radar/collectors/base.py
from abc import ABC, abstractmethod

from github_daily_radar.client import GitHubClient
from github_daily_radar.models import Candidate


class Collector(ABC):
    name: str

    def __init__(self, client: GitHubClient) -> None:
        self.client = client

    @abstractmethod
    def collect(self) -> list[Candidate]:
        raise NotImplementedError
```

- [ ] **Step 4: Re-run the client tests**

Run: `python -m pytest tests/test_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit the GitHub client layer**

```bash
git add src/github_daily_radar/client.py src/github_daily_radar/collectors/__init__.py src/github_daily_radar/collectors/base.py tests/test_client.py
git commit -m "feat: add github client and collector interface"
```

### Task 3: Add normalization, state storage, bootstrap detection, and dedupe logic

**Files:**
- Create: `src/github_daily_radar/normalize/__init__.py`
- Create: `src/github_daily_radar/normalize/candidates.py`
- Create: `src/github_daily_radar/state/__init__.py`
- Create: `src/github_daily_radar/state/store.py`
- Create: `src/github_daily_radar/scoring/__init__.py`
- Create: `src/github_daily_radar/scoring/dedupe.py`
- Create: `tests/test_normalize.py`
- Create: `tests/test_state_store.py`
- Create: `tests/test_bootstrap.py`

- [ ] **Step 1: Write the failing tests for normalization and state reads**

```python
# tests/test_normalize.py
from github_daily_radar.normalize.candidates import candidate_from_repo_search


def test_candidate_from_repo_search_maps_fields():
    item = {
        "full_name": "owner/repo",
        "html_url": "https://github.com/owner/repo",
        "owner": {"login": "owner"},
        "created_at": "2026-04-01T00:00:00Z",
        "updated_at": "2026-04-02T00:00:00Z",
        "description": "repo",
        "topics": ["agent"],
        "stargazers_count": 120,
        "forks_count": 5,
    }

    candidate = candidate_from_repo_search(item=item, source_query="topic:agent")

    assert candidate.kind == "project"
    assert candidate.repo_full_name == "owner/repo"
    assert candidate.metrics.stars == 120
```

```python
# tests/test_state_store.py
from pathlib import Path

from github_daily_radar.state.store import StateStore


def test_state_store_detects_bootstrap(tmp_path: Path):
    store = StateStore(root=tmp_path, dry_run=False, cooldown_days=14)
    assert store.detect_bootstrap() is True


def test_state_store_skips_write_on_dry_run(tmp_path: Path):
    store = StateStore(root=tmp_path, dry_run=True, cooldown_days=14)
    store.write_daily_state("2026-04-02", {"items": []})
    assert not (tmp_path / "daily" / "2026-04-02.json").exists()
```

```python
# tests/test_bootstrap.py
from github_daily_radar.scoring.dedupe import rank_weights_for_mode, should_resurface


def test_bootstrap_downweights_novelty():
    weights = rank_weights_for_mode(bootstrap=True)
    assert weights["novelty"] < weights["signal"]


def test_project_resurfaces_on_star_growth():
    assert should_resurface(
        candidate_kind="project",
        previous_metrics={"star_growth_7d": 10, "has_new_release": False},
        current_metrics={"star_growth_7d": 24, "has_new_release": False},
    ) is True
```

- [ ] **Step 2: Run the tests to verify these modules are missing**

Run: `python -m pytest tests/test_normalize.py tests/test_state_store.py tests/test_bootstrap.py -v`
Expected: FAIL with import errors for `normalize.candidates`, `state.store`, and `scoring.dedupe`

- [ ] **Step 3: Implement normalization helpers, state store, and re-entry thresholds**

```python
# src/github_daily_radar/normalize/candidates.py
from github_daily_radar.models import Candidate, CandidateMetrics


def candidate_from_repo_search(*, item: dict, source_query: str) -> Candidate:
    return Candidate(
        candidate_id=f"repo:{item['full_name']}",
        kind="project",
        source_query=source_query,
        title=item["full_name"],
        url=item["html_url"],
        repo_full_name=item["full_name"],
        author=item["owner"]["login"],
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        body_excerpt=item.get("description") or "",
        topics=item.get("topics", []),
        labels=[],
        metrics=CandidateMetrics(
            stars=item.get("stargazers_count", 0),
            forks=item.get("forks_count", 0),
        ),
        raw_signals={"search_item": item},
        dedupe_key=item["full_name"],
    )
```

```python
# src/github_daily_radar/state/store.py
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


class StateStore:
    def __init__(self, root: Path, dry_run: bool, cooldown_days: int) -> None:
        self.root = root
        self.dry_run = dry_run
        self.cooldown_days = cooldown_days

    def detect_bootstrap(self) -> bool:
        return not (self.root / "history.jsonl").exists()

    def read_history(self) -> list[dict]:
        path = self.root / "history.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def is_in_cooldown(self, dedupe_key: str, now: datetime) -> bool:
        cutoff = now - timedelta(days=self.cooldown_days)
        for row in self.read_history():
            if row["dedupe_key"] == dedupe_key and datetime.fromisoformat(row["published_at"]) >= cutoff:
                return True
        return False

    def record_published(self, rows: list[dict], published_at: datetime) -> None:
        if self.dry_run:
            return
        path = self.root / "history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for row in rows:
                payload = {"dedupe_key": row["dedupe_key"], "published_at": published_at.isoformat()}
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def write_daily_state(self, date_key: str, payload: dict) -> None:
        if self.dry_run:
            return
        daily_dir = self.root / "daily"
        daily_dir.mkdir(parents=True, exist_ok=True)
        (daily_dir / f"{date_key}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
```

```python
# src/github_daily_radar/scoring/dedupe.py
def rank_weights_for_mode(*, bootstrap: bool) -> dict[str, float]:
    if bootstrap:
        return {"novelty": 0.10, "signal": 0.45, "utility": 0.35, "taste": 0.10}
    return {"novelty": 0.30, "signal": 0.30, "utility": 0.25, "taste": 0.15}


def should_resurface(*, candidate_kind: str, previous_metrics: dict, current_metrics: dict) -> bool:
    if candidate_kind == "project":
        previous_growth = previous_metrics.get("star_growth_7d", 0)
        current_growth = current_metrics.get("star_growth_7d", 0)
        if previous_growth > 0 and current_growth >= previous_growth * 2:
            return True
        if current_metrics.get("has_new_release") and (current_metrics.get("days_since_previous_release") or 0) >= 7:
            return True
        return False

    if candidate_kind in {"discussion", "issue", "pr"}:
        previous_comments = previous_metrics.get("comments", previous_metrics.get("comment_count", 0))
        current_comments = current_metrics.get("comments", current_metrics.get("comment_count", 0))
        return previous_comments > 0 and current_comments >= previous_comments * 1.5

    return current_metrics.get("structure_score", 0) > previous_metrics.get("structure_score", 0)
```

- [ ] **Step 4: Re-run the normalization and state tests**

Run: `python -m pytest tests/test_normalize.py tests/test_state_store.py tests/test_bootstrap.py -v`
Expected: PASS

- [ ] **Step 5: Commit normalization and state tracking**

```bash
git add src/github_daily_radar/normalize/__init__.py src/github_daily_radar/normalize/candidates.py src/github_daily_radar/state/__init__.py src/github_daily_radar/state/store.py src/github_daily_radar/scoring/__init__.py src/github_daily_radar/scoring/dedupe.py tests/test_normalize.py tests/test_state_store.py tests/test_bootstrap.py
git commit -m "feat: add normalization and state tracking"
```

### Task 4: Build the project and skill collectors with real `collect()` implementations

**Files:**
- Create: `src/github_daily_radar/collectors/repos.py`
- Create: `src/github_daily_radar/collectors/skills.py`
- Create: `tests/test_repo_skill_collectors.py`

- [ ] **Step 1: Write the failing tests for repo and skill collection**

```python
# tests/test_repo_skill_collectors.py
import respx
from httpx import Response

from github_daily_radar.client import BudgetTracker, GitHubClient
from github_daily_radar.collectors.repos import RepoCollector
from github_daily_radar.collectors.skills import SkillCollector


@respx.mock
def test_repo_collector_collects_candidates():
    respx.get("https://api.github.com/search/repositories").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "full_name": "owner/repo",
                        "html_url": "https://github.com/owner/repo",
                        "owner": {"login": "owner"},
                        "created_at": "2026-04-01T00:00:00Z",
                        "updated_at": "2026-04-02T00:00:00Z",
                        "description": "repo",
                        "topics": ["agent"],
                        "stargazers_count": 100,
                        "forks_count": 5,
                    }
                ]
            },
        )
    )

    client = GitHubClient("ghs_test", BudgetTracker(total_budget=10, search_budget=5, graphql_budget=10))
    collector = RepoCollector(client=client, queries=["(topic:agent OR topic:workflow) pushed:>2026-03-26 sort:updated-desc"])

    items = collector.collect()

    assert items[0].kind == "project"


@respx.mock
def test_skill_collector_collects_candidates():
    respx.get("https://api.github.com/search/repositories").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "full_name": "owner/skills-repo",
                        "html_url": "https://github.com/owner/skills-repo",
                        "owner": {"login": "owner"},
                        "created_at": "2026-04-01T00:00:00Z",
                        "updated_at": "2026-04-02T00:00:00Z",
                        "description": "agent workflow prompts",
                        "topics": ["agent"],
                        "stargazers_count": 50,
                        "forks_count": 2,
                    }
                ]
            },
        )
    )

    client = GitHubClient("ghs_test", BudgetTracker(total_budget=10, search_budget=5, graphql_budget=10))
    collector = SkillCollector(client=client, queries=["(topic:agent OR topic:prompt) in:name,description,readme workflow prompt skill pushed:>2026-03-19 sort:stars-desc"])

    items = collector.collect()

    assert items[0].kind == "skill"
```

- [ ] **Step 2: Run the tests to verify the collectors are missing**

Run: `python -m pytest tests/test_repo_skill_collectors.py -v`
Expected: FAIL with import errors for `RepoCollector` and `SkillCollector`

- [ ] **Step 3: Implement repo and skill collectors**

```python
# src/github_daily_radar/collectors/repos.py
from github_daily_radar.collectors.base import Collector
from github_daily_radar.models import Candidate
from github_daily_radar.normalize.candidates import candidate_from_repo_search


class RepoCollector(Collector):
    name = "repos"

    def __init__(self, client, queries: list[str]) -> None:
        super().__init__(client)
        self.queries = queries

    def collect(self) -> list[Candidate]:
        candidates: list[Candidate] = []
        for query in self.queries:
            payload = self.client.search_repositories(query)
            for item in payload.get("items", []):
                candidates.append(candidate_from_repo_search(item=item, source_query=query))
        return candidates
```

```python
# src/github_daily_radar/collectors/skills.py
from github_daily_radar.collectors.base import Collector
from github_daily_radar.models import Candidate
from github_daily_radar.normalize.candidates import candidate_from_repo_search


class SkillCollector(Collector):
    name = "skills"

    def __init__(self, client, queries: list[str]) -> None:
        super().__init__(client)
        self.queries = queries

    def collect(self) -> list[Candidate]:
        candidates: list[Candidate] = []
        for query in self.queries:
            payload = self.client.search_repositories(query)
            for item in payload.get("items", []):
                candidate = candidate_from_repo_search(item=item, source_query=query)
                candidate.kind = "skill"
                candidates.append(candidate)
        return candidates
```

- [ ] **Step 4: Re-run the collector tests**

Run: `python -m pytest tests/test_repo_skill_collectors.py -v`
Expected: PASS

- [ ] **Step 5: Commit repo and skill collectors**

```bash
git add src/github_daily_radar/collectors/repos.py src/github_daily_radar/collectors/skills.py tests/test_repo_skill_collectors.py
git commit -m "feat: add repo and skill collectors"
```

### Task 5: Build discussion and issue/PR collectors with real search calls

**Files:**
- Create: `src/github_daily_radar/collectors/discussions.py`
- Create: `src/github_daily_radar/collectors/issues_prs.py`
- Create: `tests/test_discussion_collectors.py`

- [ ] **Step 1: Write the failing tests for idea-heavy thread collectors**

```python
# tests/test_discussion_collectors.py
import respx
from httpx import Response

from github_daily_radar.client import BudgetTracker, GitHubClient
from github_daily_radar.collectors.discussions import DiscussionCollector
from github_daily_radar.collectors.issues_prs import IssuesPrsCollector


@respx.mock
def test_discussion_collector_collects_high_signal_threads():
    respx.get("https://api.github.com/search/issues").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "id": 1,
                        "title": "RFC: runtime orchestration",
                        "html_url": "https://github.com/owner/repo/discussions/1",
                        "repository_url": "https://api.github.com/repos/owner/repo",
                        "user": {"login": "owner"},
                        "created_at": "2026-04-01T00:00:00Z",
                        "updated_at": "2026-04-02T00:00:00Z",
                        "body": "proposal body",
                        "comments": 18,
                        "labels": [],
                    }
                ]
            },
        )
    )

    client = GitHubClient("ghs_test", BudgetTracker(total_budget=10, search_budget=5, graphql_budget=10))
    collector = DiscussionCollector(client=client)

    items = collector.collect()

    assert items[0].kind == "discussion"


@respx.mock
def test_issues_prs_collector_classifies_pr():
    respx.get("https://api.github.com/search/issues").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "id": 2,
                        "title": "Design proposal",
                        "html_url": "https://github.com/owner/repo/pull/2",
                        "repository_url": "https://api.github.com/repos/owner/repo",
                        "user": {"login": "owner"},
                        "created_at": "2026-04-01T00:00:00Z",
                        "updated_at": "2026-04-02T00:00:00Z",
                        "body": "proposal body",
                        "comments": 12,
                        "labels": [],
                        "pull_request": {"url": "https://api.github.com/repos/owner/repo/pulls/2"},
                    }
                ]
            },
        )
    )

    client = GitHubClient("ghs_test", BudgetTracker(total_budget=10, search_budget=5, graphql_budget=10))
    collector = IssuesPrsCollector(client=client)

    items = collector.collect()

    assert items[0].kind == "pr"
```

- [ ] **Step 2: Run the tests to verify the collectors are missing**

Run: `python -m pytest tests/test_discussion_collectors.py -v`
Expected: FAIL with import errors for `DiscussionCollector` and `IssuesPrsCollector`

- [ ] **Step 3: Implement discussion and issue/PR collectors**

```python
# src/github_daily_radar/collectors/discussions.py
from github_daily_radar.collectors.base import Collector
from github_daily_radar.models import Candidate, CandidateMetrics


class DiscussionCollector(Collector):
    name = "discussions"

    def collect(self) -> list[Candidate]:
        query = 'proposal OR rfc OR idea OR design in:title,body comments:>=8'
        payload = self.client.search_issues(query)
        candidates: list[Candidate] = []
        for item in payload.get("items", []):
            candidates.append(
                Candidate(
                    candidate_id=f"discussion:{item['id']}",
                    kind="discussion",
                    source_query=query,
                    title=item["title"],
                    url=item["html_url"],
                    repo_full_name=item["repository_url"].rsplit("/repos/", 1)[-1],
                    author=item["user"]["login"],
                    created_at=item["created_at"],
                    updated_at=item["updated_at"],
                    body_excerpt=item.get("body") or "",
                    labels=[label["name"] for label in item.get("labels", [])],
                    metrics=CandidateMetrics(comments=item.get("comments", 0)),
                    raw_signals={"search_item": item},
                    dedupe_key=str(item["id"]),
                )
            )
        return candidates
```

```python
# src/github_daily_radar/collectors/issues_prs.py
from github_daily_radar.collectors.base import Collector
from github_daily_radar.models import Candidate, CandidateMetrics


class IssuesPrsCollector(Collector):
    name = "issues_prs"

    def collect(self) -> list[Candidate]:
        query = 'proposal OR roadmap OR design in:title,body comments:>=5'
        payload = self.client.search_issues(query)
        candidates: list[Candidate] = []
        for item in payload.get("items", []):
            kind = "pr" if item.get("pull_request") else "issue"
            candidates.append(
                Candidate(
                    candidate_id=f"{kind}:{item['id']}",
                    kind=kind,
                    source_query=query,
                    title=item["title"],
                    url=item["html_url"],
                    repo_full_name=item["repository_url"].rsplit("/repos/", 1)[-1],
                    author=item["user"]["login"],
                    created_at=item["created_at"],
                    updated_at=item["updated_at"],
                    body_excerpt=item.get("body") or "",
                    labels=[label["name"] for label in item.get("labels", [])],
                    metrics=CandidateMetrics(comments=item.get("comments", 0)),
                    raw_signals={"search_item": item},
                    dedupe_key=str(item["id"]),
                )
            )
        return candidates
```

- [ ] **Step 4: Re-run the collector tests**

Run: `python -m pytest tests/test_discussion_collectors.py -v`
Expected: PASS

- [ ] **Step 5: Commit discussion and issue/PR collectors**

```bash
git add src/github_daily_radar/collectors/discussions.py src/github_daily_radar/collectors/issues_prs.py tests/test_discussion_collectors.py
git commit -m "feat: add discussion and issue pr collectors"
```

### Task 6: Add rule scoring, digest rendering, Feishu card splitting, and publisher tests

**Files:**
- Create: `src/github_daily_radar/scoring/rules.py`
- Create: `src/github_daily_radar/summarize/__init__.py`
- Create: `src/github_daily_radar/summarize/digest.py`
- Create: `src/github_daily_radar/publish/__init__.py`
- Create: `src/github_daily_radar/publish/feishu.py`
- Create: `tests/test_rules.py`
- Create: `tests/test_digest_rendering.py`
- Create: `tests/test_feishu.py`

- [ ] **Step 1: Write the failing tests for scoring, grouping, and oversized digests**

```python
# tests/test_rules.py
from github_daily_radar.scoring.rules import limit_for_llm, weighted_score


def test_limit_for_llm_uses_configured_cap():
    assert limit_for_llm(list(range(100)), max_candidates=24) == list(range(24))


def test_weighted_score_sums_known_components():
    score = weighted_score({"novelty": 0.2, "signal": 0.5, "utility": 0.3, "taste": 0.1}, {"novelty": 0.3, "signal": 0.3, "utility": 0.25, "taste": 0.15})
    assert round(score, 4) == 0.315
```

```python
# tests/test_digest_rendering.py
from github_daily_radar.summarize.digest import group_digest_items


def test_group_digest_items_splits_kinds():
    sections = group_digest_items(
        [
            {"kind": "project", "title": "Repo A"},
            {"kind": "skill", "title": "Skill A"},
            {"kind": "discussion", "title": "Idea A"},
        ]
    )
    assert len(sections["projects"]) == 1
    assert len(sections["skills"]) == 1
    assert len(sections["ideas"]) == 1
```

```python
# tests/test_feishu.py
from github_daily_radar.publish.feishu import build_cards


def test_build_cards_splits_large_payload():
    items = [{"title": f"Repo {i}", "url": "https://github.com/a/b"} for i in range(30)]
    cards = build_cards(title="GitHub Daily Radar", sections={"projects": items}, metadata={"count": 30})
    assert len(cards) >= 2
    assert cards[0]["msg_type"] == "interactive"
```

- [ ] **Step 2: Run the tests to verify scoring and publishing modules are missing**

Run: `python -m pytest tests/test_rules.py tests/test_digest_rendering.py tests/test_feishu.py -v`
Expected: FAIL with import errors for `scoring.rules`, `summarize.digest`, and `publish.feishu`

- [ ] **Step 3: Implement score helpers, digest grouping, and split card rendering**

```python
# src/github_daily_radar/scoring/rules.py
def limit_for_llm(candidates: list, max_candidates: int) -> list:
    return candidates[:max_candidates]


def weighted_score(scores: dict[str, float], weights: dict[str, float]) -> float:
    return sum(scores[key] * weights[key] for key in weights)
```

```python
# src/github_daily_radar/summarize/digest.py
def group_digest_items(items: list[dict]) -> dict[str, list[dict]]:
    sections = {"projects": [], "skills": [], "ideas": [], "watchlist": []}
    for item in items:
        if item["kind"] == "project":
            sections["projects"].append(item)
        elif item["kind"] == "skill":
            sections["skills"].append(item)
        else:
            sections["ideas"].append(item)
    sections["watchlist"] = items[:2]
    return sections
```

```python
# src/github_daily_radar/publish/feishu.py
def build_cards(*, title: str, sections: dict[str, list[dict]], metadata: dict | None = None) -> list[dict]:
    flat_lines = []
    for section_name, items in sections.items():
        if not items:
            continue
        flat_lines.append(f"**{section_name}**")
        for item in items:
            flat_lines.append(f"- [{item['title']}]({item['url']})")

    chunks = [flat_lines[index:index + 20] for index in range(0, len(flat_lines), 20)] or [[]]
    cards = []
    for chunk_index, chunk in enumerate(chunks, start=1):
        elements = [{"tag": "markdown", "content": line} for line in chunk]
        if metadata and chunk_index == 1:
            elements.append({"tag": "markdown", "content": f"`meta`: {metadata}"})
        cards.append(
            {
                "msg_type": "interactive",
                "card": {
                    "config": {"wide_screen_mode": True},
                    "header": {"title": {"tag": "plain_text", "content": f"{title} ({chunk_index}/{len(chunks)})"}},
                    "elements": elements,
                },
            }
        )
    return cards
```

- [ ] **Step 4: Re-run the scoring and publishing tests**

Run: `python -m pytest tests/test_rules.py tests/test_digest_rendering.py tests/test_feishu.py -v`
Expected: PASS

- [ ] **Step 5: Commit scoring and publishing helpers**

```bash
git add src/github_daily_radar/scoring/rules.py src/github_daily_radar/summarize/__init__.py src/github_daily_radar/summarize/digest.py src/github_daily_radar/publish/__init__.py src/github_daily_radar/publish/feishu.py tests/test_rules.py tests/test_digest_rendering.py tests/test_feishu.py
git commit -m "feat: add scoring and feishu digest rendering"
```

### Task 7: Add the LLM editorial client with fallback and the full pipeline entrypoint

**Files:**
- Create: `src/github_daily_radar/summarize/llm.py`
- Create: `src/github_daily_radar/main.py`
- Create: `tests/test_llm.py`
- Create: `tests/test_main_pipeline.py`

- [ ] **Step 1: Write the failing tests for LLM HTTP calls, alert-only mode, and dry-run orchestration**

```python
# tests/test_llm.py
import respx
from httpx import Response

from github_daily_radar.summarize.llm import EditorialLLM


@respx.mock
def test_editorial_llm_posts_chat_request():
    route = respx.post("https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={"choices": [{"message": {"content": "[]"}}]},
        )
    )

    client = EditorialLLM(api_key="qwen_test", model="codingplan")
    client.rank_and_summarize([{"title": "Repo A", "kind": "project", "url": "https://github.com/a/b"}])

    assert route.called is True
```

```python
# tests/test_main_pipeline.py
from github_daily_radar.main import should_publish, should_update_state


def test_publish_and_state_skip_on_dry_run():
    assert should_publish(dry_run=True) is False
    assert should_update_state(dry_run=True) is False


def test_alert_only_short_circuits_pipeline():
    assert should_publish(dry_run=False, alert_only=True) is False
```

- [ ] **Step 2: Run the tests to verify the editorial layer and main entrypoint are missing**

Run: `python -m pytest tests/test_llm.py tests/test_main_pipeline.py -v`
Expected: FAIL with import errors for `summarize.llm` and `main`

- [ ] **Step 3: Implement the LLM client and the actual pipeline entrypoint**

```python
# src/github_daily_radar/summarize/llm.py
import httpx


class EditorialLLM:
    def __init__(self, api_key: str, model: str) -> None:
        self._http = httpx.Client(
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )
        self.model = model

    def rank_and_summarize(self, candidates: list[dict]) -> list[dict]:
        response = self._http.post(
            "/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Return compact Chinese JSON summaries for GitHub daily radar candidates. Keep facts grounded in provided fields only.",
                    },
                    {
                        "role": "user",
                        "content": str(candidates),
                    },
                ],
            },
        )
        response.raise_for_status()
        return response.json()["choices"]
```

```python
# src/github_daily_radar/main.py
import argparse
from datetime import datetime, timezone
from pathlib import Path

from github_daily_radar.client import BudgetTracker, GitHubClient
from github_daily_radar.collectors.discussions import DiscussionCollector
from github_daily_radar.collectors.issues_prs import IssuesPrsCollector
from github_daily_radar.collectors.repos import RepoCollector
from github_daily_radar.collectors.skills import SkillCollector
from github_daily_radar.config import Settings
from github_daily_radar.publish.feishu import build_cards
from github_daily_radar.scoring.dedupe import rank_weights_for_mode
from github_daily_radar.state.store import StateStore
from github_daily_radar.summarize.digest import group_digest_items
from github_daily_radar.summarize.llm import EditorialLLM


def should_publish(*, dry_run: bool, alert_only: bool = False) -> bool:
    return not dry_run and not alert_only


def should_update_state(*, dry_run: bool, alert_only: bool = False) -> bool:
    return not dry_run and not alert_only


def run_pipeline(settings: Settings, alert_only: bool = False) -> dict:
    state = StateStore(root=Path("artifacts/state"), dry_run=not should_update_state(dry_run=settings.dry_run, alert_only=alert_only), cooldown_days=settings.cooldown_days)
    if alert_only:
        return {"mode": "alert-only"}

    client = GitHubClient(
        token=settings.github_auth_token,
        budget=BudgetTracker(
            total_budget=settings.api_total_budget,
            search_budget=settings.api_search_budget,
            graphql_budget=settings.api_graphql_budget,
        ),
        search_requests_per_minute=settings.search_requests_per_minute,
    )

    collectors = [
        RepoCollector(
            client=client,
            queries=[
                "(topic:agent OR topic:workflow OR topic:automation) pushed:>2026-03-26 sort:updated-desc",
                "(topic:llm OR topic:devtools OR topic:browser-use) pushed:>2026-03-26 sort:updated-desc",
            ],
        ),
        SkillCollector(
            client=client,
            queries=[
                "(topic:agent OR topic:prompt OR topic:workflow) in:name,description,readme workflow prompt skill pushed:>2026-03-19 sort:stars-desc",
            ],
        ),
        DiscussionCollector(client=client),
        IssuesPrsCollector(client=client),
    ]

    candidates = []
    for collector in collectors:
        candidates.extend(collector.collect())

    weights = rank_weights_for_mode(bootstrap=state.detect_bootstrap())
    llm = EditorialLLM(api_key=settings.qwen_api_key, model=settings.default_model)
    editorial = llm.rank_and_summarize(
        [
            {"title": item.title, "kind": item.kind, "url": item.url, "weights": weights}
            for item in candidates[: settings.llm_max_candidates]
        ]
    )
    sections = group_digest_items([{"kind": item.kind, "title": item.title, "url": item.url} for item in candidates])
    cards = build_cards(title="GitHub Daily Radar", sections=sections, metadata={"count": len(candidates), "editorial": len(editorial)})
    state.write_daily_state(datetime.now(timezone.utc).date().isoformat(), {"cards": cards, "count": len(candidates)})
    return {"cards": cards, "count": len(candidates)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alert-only", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()
    run_pipeline(settings=settings, alert_only=args.alert_only)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Re-run the LLM and main-pipeline tests**

Run: `python -m pytest tests/test_llm.py tests/test_main_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Commit the editorial client and entrypoint**

```bash
git add src/github_daily_radar/summarize/llm.py src/github_daily_radar/main.py tests/test_llm.py tests/test_main_pipeline.py
git commit -m "feat: add editorial llm and pipeline entrypoint"
```

### Task 8: Add the GitHub Actions workflow, safe `state` sync, and execution docs

**Files:**
- Create: `.github/workflows/daily-radar.yml`
- Create: `scripts/sync_state_branch.sh`
- Create: `tests/test_workflow_config.py`
- Create: `README.md`

- [ ] **Step 1: Write the failing tests for `dry_run`, concurrency, alerting, and worktree sync**

```python
# tests/test_workflow_config.py
from pathlib import Path


def test_workflow_contains_dry_run_and_concurrency():
    workflow = Path(".github/workflows/daily-radar.yml").read_text(encoding="utf-8")
    assert "dry_run:" in workflow
    assert "concurrency:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "if: failure()" in workflow
    assert "bash scripts/sync_state_branch.sh" in workflow


def test_state_sync_script_uses_worktree():
    script = Path("scripts/sync_state_branch.sh").read_text(encoding="utf-8")
    assert "git worktree add" in script
```

- [ ] **Step 2: Run the tests before the workflow exists**

Run: `python -m pytest tests/test_workflow_config.py -v`
Expected: FAIL with `FileNotFoundError` for workflow and sync script

- [ ] **Step 3: Create the workflow and safe state-sync script**

```yaml
# .github/workflows/daily-radar.yml
name: daily-radar

on:
  schedule:
    - cron: '15 1 * * *'
  workflow_dispatch:
    inputs:
      dry_run:
        description: 'Run without publishing or updating state'
        required: false
        default: false
        type: boolean

concurrency:
  group: github-daily-radar
  cancel-in-progress: false

jobs:
  radar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --extra dev
      - run: uv run python -m github_daily_radar.main
        env:
          DRY_RUN: ${{ inputs.dry_run || false }}
          TIMEZONE: Asia/Shanghai
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_PAT: ${{ secrets.GITHUB_PAT }}
          QWEN_API_KEY: ${{ secrets.QWEN_API_KEY }}
          FEISHU_WEBHOOK_URL: ${{ secrets.FEISHU_WEBHOOK_URL }}
      - run: bash scripts/sync_state_branch.sh
        if: ${{ !inputs.dry_run }}
      - name: Send failure alert
        if: failure()
        run: uv run python -m github_daily_radar.main --alert-only
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_PAT: ${{ secrets.GITHUB_PAT }}
          QWEN_API_KEY: ${{ secrets.QWEN_API_KEY }}
          FEISHU_WEBHOOK_URL: ${{ secrets.FEISHU_WEBHOOK_URL }}
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: daily-radar-artifacts
          path: artifacts/
```

```bash
# scripts/sync_state_branch.sh
set -euo pipefail

STATE_DIR="$(mktemp -d)"
git fetch origin state || true

if git show-ref --verify --quiet refs/remotes/origin/state; then
  git worktree add "$STATE_DIR" origin/state
else
  git worktree add --detach "$STATE_DIR"
  (
    cd "$STATE_DIR"
    git checkout --orphan state
    git rm -rf . >/dev/null 2>&1 || true
  )
fi

mkdir -p "$STATE_DIR/state"
cp -R artifacts/state/. "$STATE_DIR/state/"

(
  cd "$STATE_DIR"
  git add state
  git diff --cached --quiet || git commit -m "chore: update radar state"
  git push origin HEAD:state
)

git worktree remove "$STATE_DIR" --force
```

```text
# README.md

Local setup:

uv sync --extra dev
uv run python -m github_daily_radar.main

Dry run:

DRY_RUN=true uv run python -m github_daily_radar.main
```

- [ ] **Step 4: Re-run the workflow tests and the full fast suite**

Run: `python -m pytest tests/test_config.py tests/test_models.py tests/test_client.py tests/test_normalize.py tests/test_state_store.py tests/test_bootstrap.py tests/test_repo_skill_collectors.py tests/test_discussion_collectors.py tests/test_rules.py tests/test_digest_rendering.py tests/test_feishu.py tests/test_llm.py tests/test_main_pipeline.py tests/test_workflow_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit the workflow, sync script, and docs**

```bash
git add .github/workflows/daily-radar.yml scripts/sync_state_branch.sh README.md tests/test_workflow_config.py
git commit -m "feat: add scheduled workflow and safe state sync"
```
