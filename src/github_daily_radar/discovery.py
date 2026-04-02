from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import yaml

DEFAULT_DISCUSSION_KEYWORDS = ["proposal", "rfc", "idea", "design"]
DEFAULT_ISSUE_KEYWORDS = ["proposal", "roadmap", "design"]

_DEFAULT_SEED_REPOS = [
    "langchain-ai/langchain",
    "microsoft/autogen",
    "openai/openai-agents-python",
    "anthropics/claude-code",
    "browser-use/browser-use",
    "modelcontextprotocol/specification",
    "vllm-project/vllm",
    "huggingface/transformers",
    "crewAIInc/crewAI",
    "lobehub/lobe-chat",
    "pydantic/pydantic-ai",
    "obra/superpowers",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_seed_repos(path: Path | None = None) -> list[str]:
    config_path = path or _repo_root() / "seed_repos.yaml"
    if not config_path.exists():
        return list(_DEFAULT_SEED_REPOS)

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    seed_repos = raw.get("seed_repos") or _DEFAULT_SEED_REPOS
    return [repo for repo in seed_repos if isinstance(repo, str) and repo.strip()]


def recent_date(*, days: int, now: datetime | None = None) -> str:
    moment = now or datetime.now(timezone.utc)
    cutoff = moment.astimezone(timezone.utc) - timedelta(days=days)
    return cutoff.strftime("%Y-%m-%d")


def _chunked(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def build_repo_queries(*, now: datetime | None = None) -> list[str]:
    cutoff = recent_date(days=7, now=now)
    return [
        f"(topic:agent OR topic:workflow OR topic:automation) pushed:>{cutoff} sort:updated-desc",
        f"(topic:llm OR topic:devtools OR topic:browser-use) pushed:>{cutoff} sort:updated-desc",
    ]


def build_skill_queries(*, now: datetime | None = None) -> list[str]:
    cutoff = recent_date(days=14, now=now)
    return [
        f"(topic:agent OR topic:prompt OR topic:workflow) in:name,description,readme workflow prompt skill pushed:>{cutoff} sort:stars-desc",
    ]


def _repo_clause(repos: list[str]) -> str:
    return " OR ".join(f"repo:{repo}" for repo in repos)


def build_discussion_queries(
    *,
    seed_repos: list[str] | None = None,
    now: datetime | None = None,
    chunk_size: int = 4,
) -> list[str]:
    repos = seed_repos or load_seed_repos()
    cutoff = recent_date(days=14, now=now)
    keyword_clause = " OR ".join(DEFAULT_DISCUSSION_KEYWORDS)
    queries: list[str] = []
    for chunk in _chunked(repos, chunk_size):
        queries.append(
            f"({_repo_clause(chunk)}) is:issue "
            f"({keyword_clause}) in:title,body comments:>=8 updated:>{cutoff} sort:updated-desc"
        )
    return queries


def build_issue_pr_queries(
    *,
    seed_repos: list[str] | None = None,
    now: datetime | None = None,
    chunk_size: int = 4,
) -> list[str]:
    repos = seed_repos or load_seed_repos()
    cutoff = recent_date(days=14, now=now)
    keyword_clause = " OR ".join(DEFAULT_ISSUE_KEYWORDS)
    queries: list[str] = []
    for chunk in _chunked(repos, chunk_size):
        queries.append(
            f"({_repo_clause(chunk)}) is:pr "
            f"({keyword_clause}) in:title,body comments:>=5 updated:>{cutoff} sort:updated-desc"
        )
    return queries
