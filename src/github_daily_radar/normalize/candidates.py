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


def _coerce_int(value: object) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def candidate_from_code_search(*, item: dict, source_query: str) -> Candidate:
    repository = item.get("repository") or {}
    candidate = candidate_from_repo_search(item=repository, source_query=source_query, kind="skill")
    candidate.raw_signals = {
        **candidate.raw_signals,
        "code_search_item": item,
        "matched_file": item.get("name") or "",
        "matched_path": item.get("path") or "",
    }
    candidate.rule_scores = {
        **candidate.rule_scores,
        "code_search_hit": 1.0,
    }
    return candidate


def candidate_from_repo_search(*, item: dict, source_query: str, kind: str = "project") -> Candidate:
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
        candidate_id=f"{kind}:{full_name}",
        kind=kind,
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
        dedupe_key=f"{kind}:{full_name}",
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


def candidate_from_ossinsight_repo(*, item: dict, source_query: str, collection_name: str | None = None) -> Candidate:
    repo_full_name = _pick_first(item, ("repo_name", "nameWithOwner", "full_name"), "unknown/unknown")
    url = _pick_first(item, ("repo_url", "url"), f"https://github.com/{repo_full_name}")
    description = item.get("description") or item.get("repo_description") or item.get("repo_about") or ""
    created_at = _utc_now_iso()
    updated_at = _utc_now_iso()
    stars = item.get("current_period_growth", item.get("stars", item.get("star_growth", 0)))
    forks = item.get("forks", item.get("fork_count", 0))
    total_score = item.get("total_score", item.get("total", 0))
    collection_names = item.get("collection_names")
    if isinstance(collection_names, list):
        topics = [str(name) for name in collection_names if isinstance(name, str) and name.strip()]
    elif isinstance(collection_names, str):
        topics = [part.strip() for part in collection_names.split(",") if part.strip()]
    else:
        topics = []
    if collection_name and collection_name not in topics:
        topics.insert(0, collection_name)

    owner = repo_full_name.split("/", 1)[0] if "/" in repo_full_name else ""
    kind = "project"
    return Candidate(
        candidate_id=f"{kind}:{repo_full_name}",
        kind=kind,
        source_query=source_query,
        title=repo_full_name,
        url=url,
        repo_full_name=repo_full_name,
        author=owner,
        created_at=created_at,
        updated_at=updated_at,
        body_excerpt=description,
        topics=topics,
        labels=[],
        metrics=CandidateMetrics(
            stars=_coerce_int(stars),
            forks=_coerce_int(forks),
            reactions=_coerce_int(total_score),
            star_growth_7d=_coerce_int(stars),
        ),
        raw_signals={"ossinsight_item": item, "collection_name": collection_name},
        rule_scores={
            "ossinsight_total_score": float(total_score or 0),
            "ossinsight_source": source_query,
            "ossinsight_collection": collection_name or "",
        },
        dedupe_key=repo_full_name,
    )
