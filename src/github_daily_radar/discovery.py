from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import yaml

DEFAULT_TOPICS = [
    "agent",
    "ai-agents",
    "agentic-workflow",
    "browser-use",
    "computer-use",
    "ai-coding",
    "coding-assistant",
    "swe-agent",
    "mcp",
    "model-context-protocol",
    "tool-use",
    "llm",
    "vlm",
    "llm-inference",
    "rag",
    "graphrag",
    "cursor-rules",
    "ai-prompts",
]
DEFAULT_SEED_ORGS = [
    "openai",
    "anthropics",
    "google-deepmind",
    "meta-llama",
    "huggingface",
    "mistralai",
    "vllm-project",
    "langchain-ai",
    "modelcontextprotocol",
    "QwenLM",
    "crewAIInc",
    "All-Hands-AI",
]
DEFAULT_SKILL_SEED_REPOS = [
    "obra/superpowers",
    "PatrickJS/awesome-cursorrules",
    "pontusab/cursor.directory",
    "anthropics/anthropic-cookbook",
    "openai/openai-cookbook",
    "punkpeye/awesome-mcp-servers",
    "f/awesome-chatgpt-prompts",
    "lobehub/lobe-chat-agents",
]
DEFAULT_SKILL_CODE_QUERIES = [
    "filename:SKILL.md path:skills",
    "filename:.cursorrules OR filename:cursorrules.md",
    "filename:CLAUDE.md NOT repo:anthropics/claude-code",
    "filename:AGENTS.md NOT repo:openai/openai-agents-python",
]
DEFAULT_SKILL_REPO_QUERIES = [
    "cursor rules AI in:name,description",
    "claude skills agent prompt in:name,description",
    "mcp server tool in:name,description",
]
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


def _config_paths(path: Path | None = None) -> list[Path]:
    if path is not None:
        return [path]
    return [
        _repo_root() / "config" / "radar.yaml",
        _repo_root() / "seed_repos.yaml",
    ]


def load_radar_config(path: Path | None = None) -> dict:
    for config_path in _config_paths(path):
        if not config_path.exists():
            continue
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return raw if isinstance(raw, dict) else {}
    return {}


def load_seed_repos(path: Path | None = None) -> list[str]:
    raw = load_radar_config(path)
    if not raw:
        return list(_DEFAULT_SEED_REPOS)

    seed_repos = raw.get("seed_repos") or _DEFAULT_SEED_REPOS
    return [repo for repo in seed_repos if isinstance(repo, str) and repo.strip()]


def load_topics(path: Path | None = None) -> list[str]:
    raw = load_radar_config(path)
    topics = raw.get("topics") or DEFAULT_TOPICS
    return [topic for topic in topics if isinstance(topic, str) and topic.strip()]


def load_seed_orgs(path: Path | None = None) -> list[str]:
    raw = load_radar_config(path)
    seed_orgs = raw.get("seed_orgs") or DEFAULT_SEED_ORGS
    return [org for org in seed_orgs if isinstance(org, str) and org.strip()]


def load_skill_seed_repos(path: Path | None = None) -> list[str]:
    raw = load_radar_config(path)
    skill_section = raw.get("skills") if isinstance(raw.get("skills"), dict) else {}
    seed_skill_repos = skill_section.get("seed_skill_repos") or DEFAULT_SKILL_SEED_REPOS
    return [repo for repo in seed_skill_repos if isinstance(repo, str) and repo.strip()]


def load_skill_code_queries(path: Path | None = None) -> list[str]:
    raw = load_radar_config(path)
    skill_section = raw.get("skills") if isinstance(raw.get("skills"), dict) else {}
    code_queries = skill_section.get("code_search_queries") or DEFAULT_SKILL_CODE_QUERIES
    return [query for query in code_queries if isinstance(query, str) and query.strip()]


def load_skill_repo_queries(path: Path | None = None) -> list[str]:
    raw = load_radar_config(path)
    skill_section = raw.get("skills") if isinstance(raw.get("skills"), dict) else {}
    repo_queries = skill_section.get("repo_search_queries") or DEFAULT_SKILL_REPO_QUERIES
    return [query for query in repo_queries if isinstance(query, str) and query.strip()]


def load_discussion_keywords(path: Path | None = None) -> list[str]:
    raw = load_radar_config(path)
    keywords = raw.get("discussion_keywords") or DEFAULT_DISCUSSION_KEYWORDS
    return [keyword for keyword in keywords if isinstance(keyword, str) and keyword.strip()]


def load_issue_pr_keywords(path: Path | None = None) -> list[str]:
    raw = load_radar_config(path)
    keywords = raw.get("issue_pr_keywords") or DEFAULT_ISSUE_KEYWORDS
    return [keyword for keyword in keywords if isinstance(keyword, str) and keyword.strip()]


def recent_date(*, days: int, now: datetime | None = None) -> str:
    moment = now or datetime.now(timezone.utc)
    cutoff = moment.astimezone(timezone.utc) - timedelta(days=days)
    return cutoff.strftime("%Y-%m-%d")


def _chunked(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _balanced_groups(values: list[str], group_count: int) -> list[list[str]]:
    cleaned = [value for value in values if isinstance(value, str) and value.strip()]
    if not cleaned or group_count <= 0:
        return []
    group_count = min(group_count, len(cleaned))
    base_size, remainder = divmod(len(cleaned), group_count)
    groups: list[list[str]] = []
    start = 0
    for index in range(group_count):
        size = base_size + (1 if index < remainder else 0)
        if size <= 0:
            continue
        groups.append(cleaned[start : start + size])
        start += size
    return groups


def _quote_keyword(keyword: str) -> str:
    keyword = keyword.strip()
    if " " in keyword and not (keyword.startswith('"') and keyword.endswith('"')):
        return f'"{keyword}"'
    return keyword


def _keyword_clause(keywords: list[str]) -> str:
    return " OR ".join(_quote_keyword(keyword) for keyword in keywords if keyword.strip())


def _date_clause(*, field: str, days_back: int | None, now: datetime | None = None) -> str:
    if days_back is None:
        return ""
    return f" {field}:>{recent_date(days=days_back, now=now)}"


def build_repo_queries(*, now: datetime | None = None, days_back: int | None = None) -> list[str]:
    date_clause = _date_clause(field="pushed", days_back=days_back, now=now)
    topics = load_topics()
    seed_orgs = load_seed_orgs()
    topic_groups = list(_chunked(topics, min(6, max(1, len(topics) // 3 or 1))))
    org_groups = _balanced_groups(seed_orgs, 3)
    moment = now or datetime.now(timezone.utc)
    org_group = org_groups[moment.astimezone(timezone.utc).date().toordinal() % len(org_groups)] if org_groups else []
    queries = []
    for group in topic_groups[:3]:
        topic_clause = " OR ".join(f"topic:{topic}" for topic in group)
        queries.append(f"({topic_clause}){date_clause}")
    if org_group:
        org_clause = " OR ".join(f"org:{org}" for org in org_group)
        queries.append(f"({org_clause}){date_clause}")
    return queries


def build_skill_queries(*, now: datetime | None = None, days_back: int | None = None) -> list[str]:
    date_clause = _date_clause(field="pushed", days_back=days_back, now=now)
    return [
        f"(skill OR prompt OR workflow OR agent OR automation) in:name,description,readme{date_clause}",
    ]


def build_skill_code_queries() -> list[str]:
    return load_skill_code_queries()


def build_skill_repo_queries(*, now: datetime | None = None, days_back: int | None = None) -> list[str]:
    date_clause = _date_clause(field="pushed", days_back=days_back, now=now)
    return [f"{query}{date_clause}".strip() for query in load_skill_repo_queries()]


def _repo_clause(repos: list[str]) -> str:
    return " OR ".join(f"repo:{repo}" for repo in repos)


def build_discussion_queries(
    *,
    seed_repos: list[str] | None = None,
    now: datetime | None = None,
    chunk_size: int = 4,
    days_back: int | None = None,
) -> list[str]:
    repos = seed_repos or load_seed_repos()
    chunk_size = min(max(1, chunk_size), 4)
    date_clause = _date_clause(field="updated", days_back=days_back, now=now)
    keyword_groups = _balanced_groups(load_discussion_keywords(), max(1, len(list(_chunked(repos, chunk_size)))))
    queries: list[str] = []
    repo_groups = list(_chunked(repos, chunk_size))
    for index, chunk in enumerate(repo_groups):
        keyword_group = keyword_groups[index] if index < len(keyword_groups) else keyword_groups[-1] if keyword_groups else []
        keyword_clause = _keyword_clause(keyword_group)
        keyword_part = f" ({keyword_clause})" if keyword_clause else ""
        queries.append(
            f"({_repo_clause(chunk)}) is:issue{keyword_part} "
            f"in:title comments:>=3{date_clause}"
        )
    return queries


def build_issue_pr_queries(
    *,
    seed_repos: list[str] | None = None,
    now: datetime | None = None,
    chunk_size: int = 4,
    days_back: int | None = None,
) -> list[str]:
    repos = seed_repos or load_seed_repos()
    chunk_size = min(max(1, chunk_size), 4)
    date_clause = _date_clause(field="updated", days_back=days_back, now=now)
    keyword_groups = _balanced_groups(load_issue_pr_keywords(), max(1, len(list(_chunked(repos, chunk_size)))))
    queries: list[str] = []
    repo_groups = list(_chunked(repos, chunk_size))
    for index, chunk in enumerate(repo_groups):
        keyword_group = keyword_groups[index] if index < len(keyword_groups) else keyword_groups[-1] if keyword_groups else []
        keyword_clause = _keyword_clause(keyword_group)
        keyword_part = f" ({keyword_clause})" if keyword_clause else ""
        queries.append(
            f"({_repo_clause(chunk)}) is:open{keyword_part} "
            f"in:title comments:>=1{date_clause}"
        )
    return queries
