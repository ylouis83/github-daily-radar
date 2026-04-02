from datetime import datetime, timezone

from github_daily_radar.models import Candidate, CandidateMetrics


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _pick_first(item: dict, keys: tuple[str, ...], default: str) -> str:
    for key in keys:
        value = item.get(key)
        if value:
            return value
    return default


def candidate_from_code_search(*, item: dict, source_query: str) -> Candidate:
    repository = item.get("repository") or {}
    return candidate_from_repo_search(item=repository, source_query=source_query)


def candidate_from_repo_search(*, item: dict, source_query: str) -> Candidate:
    full_name = _pick_first(item, ("full_name", "nameWithOwner"), "unknown/unknown")
    created_at = _pick_first(
        item,
        ("created_at", "createdAt", "updated_at", "updatedAt"),
        _utc_now_iso(),
    )
    updated_at = _pick_first(
        item,
        ("updated_at", "updatedAt", "created_at", "createdAt"),
        created_at,
    )
    url = _pick_first(item, ("html_url", "url"), f"https://github.com/{full_name}")
    return Candidate(
        candidate_id=f"repo:{full_name}",
        kind="project",
        source_query=source_query,
        title=full_name,
        url=url,
        repo_full_name=full_name,
        author=item.get("owner", {}).get("login", ""),
        created_at=created_at,
        updated_at=updated_at,
        body_excerpt=item.get("description") or "",
        topics=item.get("topics", []),
        labels=[],
        metrics=CandidateMetrics(
            stars=item.get("stargazers_count", item.get("stargazerCount", 0)),
            forks=item.get("forks_count", item.get("forkCount", 0)),
        ),
        raw_signals={"search_item": item},
        rule_scores={},
        dedupe_key=full_name,
    )


def candidate_from_issue_search(*, item: dict, source_query: str, kind: str = "issue") -> Candidate:
    created_at = _pick_first(item, ("created_at", "createdAt"), _utc_now_iso())
    updated_at = _pick_first(item, ("updated_at", "updatedAt", "created_at", "createdAt"), created_at)
    return Candidate(
        candidate_id=f"{kind}:{item['id']}",
        kind=kind,
        source_query=source_query,
        title=item["title"],
        url=item["html_url"],
        repo_full_name=item["repository_url"].rsplit("/repos/", 1)[-1],
        author=item.get("user", {}).get("login", ""),
        created_at=created_at,
        updated_at=updated_at,
        body_excerpt=item.get("body") or "",
        topics=[],
        labels=[label["name"] for label in item.get("labels", [])],
        metrics=CandidateMetrics(comments=item.get("comments", 0)),
        raw_signals={"search_item": item},
        rule_scores={},
        dedupe_key=str(item["id"]),
    )


def candidate_from_graphql_repo(*, item: dict, source_query: str) -> Candidate:
    topics = [node["topic"]["name"] for node in item.get("repositoryTopics", {}).get("nodes", []) if node.get("topic")]
    latest_release = item.get("releases", {}).get("nodes", [])
    release = latest_release[0] if latest_release else None
    created_at = _pick_first(item, ("createdAt", "updatedAt"), _utc_now_iso())
    updated_at = _pick_first(item, ("updatedAt", "createdAt"), created_at)
    return Candidate(
        candidate_id=f"repo:{item['nameWithOwner']}",
        kind="skill",
        source_query=source_query,
        title=item["nameWithOwner"],
        url=item["url"],
        repo_full_name=item["nameWithOwner"],
        author=item.get("owner", {}).get("login", ""),
        created_at=created_at,
        updated_at=updated_at,
        body_excerpt=item.get("description") or "",
        topics=topics,
        labels=[],
        metrics=CandidateMetrics(
            stars=item.get("stargazerCount", 0),
            forks=item.get("forkCount", 0),
            has_new_release=bool(release),
        ),
        raw_signals={"graphql_item": item, "latest_release": release},
        rule_scores={},
        dedupe_key=item["nameWithOwner"],
    )
