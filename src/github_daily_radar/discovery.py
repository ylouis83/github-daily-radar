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
    "ai-boost/awesome-prompts",
    "langchain-ai/langgraph/examples",
    "crewAIInc/crewAI-examples",
    "lobehub/lobe-chat-agents",
]
DEFAULT_SKILL_CODE_QUERIES = [
    "filename:SKILL.md path:skills",
    "filename:.cursorrules OR filename:cursorrules.md",
    "filename:CLAUDE.md NOT repo:anthropics/claude-code",
    "filename:AGENTS.md NOT repo:openai/openai-agents-python",
    "filename:copilot-instructions.md",
    "filename:mcp.json",
]
DEFAULT_SKILL_REPO_QUERIES = [
    "cursor rules AI in:name,description",
    "claude skills agent prompt in:name,description",
    "mcp server tool in:name,description",
    "agent workflow prompt in:name,description",
]
DEFAULT_SKILL_MIN_STARS = 80
DEFAULT_PROJECT_MIN_STARS = 120
DEFAULT_SKILL_SHAPE_FLOOR = 3
DEFAULT_SKILL_TOP_N = 20
DEFAULT_SKILL_PER_REPO_CAP = 1
DEFAULT_DAILY_ITEM_COUNT_MIN = 10
DEFAULT_DAILY_ITEM_COUNT_MAX = 20
DEFAULT_DAILY_ITEM_PROJECT_FIRST = True
DEFAULT_DISCUSSION_KEYWORDS = ["proposal", "rfc", "idea", "design"]
DEFAULT_ISSUE_KEYWORDS = ["proposal", "roadmap", "design"]
DEFAULT_OSSINSIGHT_PERIODS = ["past_24_hours", "past_7_days"]
DEFAULT_OSSINSIGHT_LANGUAGE = "All"
DEFAULT_OSSINSIGHT_COLLECTION_PERIOD = "past_28_days"
DEFAULT_OSSINSIGHT_COLLECTION_NAME_KEYWORDS = [
    "agent",
    "ai-agents",
    "agentic",
    "browser-use",
    "computer-use",
    "llm",
    "rag",
    "prompt",
    "mcp",
    "coding-assistant",
    "ai-coding",
    "inference",
]
DEFAULT_OSSINSIGHT_COLLECTION_NAME_EXCLUDES = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "tensorflow",
    "pytorch",
    "scikit-learn",
    "keras",
]
DEFAULT_OSSINSIGHT_MAX_TRENDING_ITEMS = 20
DEFAULT_OSSINSIGHT_MAX_COLLECTION_IDS = 3

_DEFAULT_SEED_REPOS = [
    "modelcontextprotocol/specification",
    "modelcontextprotocol/servers",
    "anthropics/claude-code",
    "cline/cline",
    "All-Hands-AI/OpenHands",
    "paul-gauthier/aider",
    "langchain-ai/langgraph",
    "browser-use/browser-use",
    "openai/openai-agents-python",
    "pydantic/pydantic-ai",
    "huggingface/smolagents",
    "microsoft/autogen",
    "run-llama/llama_index",
    "langgenius/dify",
    "open-webui/open-webui",
    "vllm-project/vllm",
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


def load_skill_ranking_config(path: Path | None = None) -> dict:
    raw = load_radar_config(path)
    skill_section = raw.get("skills") if isinstance(raw.get("skills"), dict) else {}
    ranking = skill_section.get("ranking") if isinstance(skill_section.get("ranking"), dict) else {}
    return ranking or {}


def _load_skill_ranking_int(path: Path | None, key: str, default: int) -> int:
    raw = load_skill_ranking_config(path)
    value = raw.get(key, default)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def load_skill_min_stars(path: Path | None = None) -> int:
    return _load_skill_ranking_int(path, "skill_min_stars", DEFAULT_SKILL_MIN_STARS)


def load_project_min_stars(path: Path | None = None) -> int:
    return _load_skill_ranking_int(path, "project_min_stars", DEFAULT_PROJECT_MIN_STARS)


def load_skill_shape_floor(path: Path | None = None) -> int:
    return _load_skill_ranking_int(path, "skill_shape_floor", DEFAULT_SKILL_SHAPE_FLOOR)


def load_skill_top_n(path: Path | None = None) -> int:
    return _load_skill_ranking_int(path, "top_n", DEFAULT_SKILL_TOP_N)


def load_skill_per_repo_cap(path: Path | None = None) -> int:
    return _load_skill_ranking_int(path, "per_repo_cap", DEFAULT_SKILL_PER_REPO_CAP)


def load_output_daily_item_count_config(path: Path | None = None) -> dict[str, int | bool]:
    raw = load_radar_config(path)
    output = raw.get("output") if isinstance(raw.get("output"), dict) else {}
    daily_item_count = output.get("daily_item_count") if isinstance(output.get("daily_item_count"), dict) else {}

    min_items = daily_item_count.get("min", DEFAULT_DAILY_ITEM_COUNT_MIN)
    max_items = daily_item_count.get("max", DEFAULT_DAILY_ITEM_COUNT_MAX)
    project_first = daily_item_count.get("project_first", DEFAULT_DAILY_ITEM_PROJECT_FIRST)

    try:
        min_value = max(1, int(min_items))
    except (TypeError, ValueError):
        min_value = DEFAULT_DAILY_ITEM_COUNT_MIN
    try:
        max_value = max(min_value, int(max_items))
    except (TypeError, ValueError):
        max_value = max(DEFAULT_DAILY_ITEM_COUNT_MAX, min_value)

    return {
        "min": min_value,
        "max": max_value,
        "project_first": bool(project_first),
    }


def load_discussion_keywords(path: Path | None = None) -> list[str]:
    raw = load_radar_config(path)
    keywords = raw.get("discussion_keywords") or DEFAULT_DISCUSSION_KEYWORDS
    return [keyword for keyword in keywords if isinstance(keyword, str) and keyword.strip()]


def load_issue_pr_keywords(path: Path | None = None) -> list[str]:
    raw = load_radar_config(path)
    keywords = raw.get("issue_pr_keywords") or DEFAULT_ISSUE_KEYWORDS
    return [keyword for keyword in keywords if isinstance(keyword, str) and keyword.strip()]


def load_ossinsight_config(path: Path | None = None) -> dict:
    raw = load_radar_config(path)
    ossinsight = raw.get("ossinsight") if isinstance(raw.get("ossinsight"), dict) else {}
    return ossinsight or {}


def load_ossinsight_enabled(path: Path | None = None) -> bool:
    return bool(load_ossinsight_config(path).get("enabled", True))


def load_ossinsight_trending_periods(path: Path | None = None) -> list[str]:
    raw = load_ossinsight_config(path)
    periods = raw.get("trending_periods") or DEFAULT_OSSINSIGHT_PERIODS
    return [period for period in periods if isinstance(period, str) and period.strip()]


def load_ossinsight_language(path: Path | None = None) -> str:
    raw = load_ossinsight_config(path)
    language = raw.get("language") or DEFAULT_OSSINSIGHT_LANGUAGE
    return language if isinstance(language, str) and language.strip() else DEFAULT_OSSINSIGHT_LANGUAGE


def load_ossinsight_collection_period(path: Path | None = None) -> str:
    raw = load_ossinsight_config(path)
    period = raw.get("collection_period") or DEFAULT_OSSINSIGHT_COLLECTION_PERIOD
    return period if isinstance(period, str) and period.strip() else DEFAULT_OSSINSIGHT_COLLECTION_PERIOD


def load_ossinsight_collection_name_keywords(path: Path | None = None) -> list[str]:
    raw = load_ossinsight_config(path)
    keywords = raw.get("collection_name_keywords") or DEFAULT_OSSINSIGHT_COLLECTION_NAME_KEYWORDS
    return [keyword for keyword in keywords if isinstance(keyword, str) and keyword.strip()]


def load_ossinsight_collection_name_excludes(path: Path | None = None) -> list[str]:
    raw = load_ossinsight_config(path)
    excludes = raw.get("collection_name_exclude_keywords") or DEFAULT_OSSINSIGHT_COLLECTION_NAME_EXCLUDES
    return [keyword for keyword in excludes if isinstance(keyword, str) and keyword.strip()]


def load_ossinsight_max_trending_items(path: Path | None = None) -> int:
    raw = load_ossinsight_config(path)
    value = raw.get("max_trending_items", DEFAULT_OSSINSIGHT_MAX_TRENDING_ITEMS)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return DEFAULT_OSSINSIGHT_MAX_TRENDING_ITEMS


def load_ossinsight_max_collection_ids(path: Path | None = None) -> int:
    raw = load_ossinsight_config(path)
    value = raw.get("max_collection_ids", DEFAULT_OSSINSIGHT_MAX_COLLECTION_IDS)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return DEFAULT_OSSINSIGHT_MAX_COLLECTION_IDS


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


def cycle_queries(queries: list[str], *, limit: int, seed: int = 0) -> list[str]:
    cleaned = [query for query in queries if isinstance(query, str) and query.strip()]
    if limit <= 0 or not cleaned:
        return []
    if limit >= len(cleaned):
        return cleaned
    offset = seed % len(cleaned)
    rotated = cleaned[offset:] + cleaned[:offset]
    return rotated[:limit]


def build_repo_queries(*, now: datetime | None = None, days_back: int | None = 7) -> list[str]:
    date_clause = _date_clause(field="pushed", days_back=days_back, now=now)
    topics = load_topics()
    seed_orgs = load_seed_orgs()
    moment = now or datetime.now(timezone.utc)
    seed = moment.astimezone(timezone.utc).date().toordinal()
    topic_queries = [f"(topic:{topic}){date_clause}" for topic in topics]
    org_queries = [f"(org:{org}){date_clause}" for org in seed_orgs]
    queries = cycle_queries(topic_queries, limit=min(3, len(topic_queries)), seed=seed)
    queries.extend(cycle_queries(org_queries, limit=min(1, len(org_queries)), seed=seed + 1))
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
    max_queries: int = 4,
    days_back: int | None = 30,
) -> list[str]:
    repos = seed_repos or load_seed_repos()
    date_clause = _date_clause(field="updated", days_back=days_back, now=now)
    repo_groups = _balanced_groups(repos, min(max_queries, len(repos)))
    keyword_groups = _balanced_groups(load_discussion_keywords(), max(1, len(repo_groups)))
    queries: list[str] = []
    for index, chunk in enumerate(repo_groups):
        keyword_group = keyword_groups[index] if index < len(keyword_groups) else keyword_groups[-1] if keyword_groups else []
        keyword_clause = _keyword_clause(keyword_group)
        keyword_part = f" ({keyword_clause})" if keyword_clause else ""
        comments_clause = " comments:>=5" if index < 2 else " comments:>=3"
        queries.append(
            f"({_repo_clause(chunk)}) is:issue{keyword_part} "
            f"in:title{comments_clause}{date_clause}"
        )
    return queries


def build_issue_pr_queries(
    *,
    seed_repos: list[str] | None = None,
    now: datetime | None = None,
    max_queries: int = 4,
    days_back: int | None = 30,
) -> list[str]:
    repos = seed_repos or load_seed_repos()
    date_clause = _date_clause(field="updated", days_back=days_back, now=now)
    repo_groups = _balanced_groups(repos, min(max_queries, len(repos)))
    keyword_groups = _balanced_groups(load_issue_pr_keywords(), max(1, len(repo_groups)))
    queries: list[str] = []
    for index, chunk in enumerate(repo_groups):
        keyword_group = keyword_groups[index] if index < len(keyword_groups) else keyword_groups[-1] if keyword_groups else []
        keyword_clause = _keyword_clause(keyword_group)
        keyword_part = f" ({keyword_clause})" if keyword_clause else ""
        comments_clause = " comments:>=3" if index < 2 else ""
        queries.append(
            f"({_repo_clause(chunk)}) is:open{keyword_part} "
            f"in:title{comments_clause}{date_clause}"
        )
    return queries
