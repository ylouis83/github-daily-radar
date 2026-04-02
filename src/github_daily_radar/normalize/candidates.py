from github_daily_radar.models import Candidate, CandidateMetrics


def candidate_from_code_search(*, item: dict, source_query: str) -> Candidate:
    repository = item["repository"]
    return candidate_from_repo_search(item=repository, source_query=source_query)


def candidate_from_repo_search(*, item: dict, source_query: str) -> Candidate:
    return Candidate(
        candidate_id=f"repo:{item['full_name']}",
        kind="project",
        source_query=source_query,
        title=item["full_name"],
        url=item["html_url"],
        repo_full_name=item["full_name"],
        author=item.get("owner", {}).get("login", ""),
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
        rule_scores={},
        dedupe_key=item["full_name"],
    )


def candidate_from_issue_search(*, item: dict, source_query: str, kind: str = "issue") -> Candidate:
    return Candidate(
        candidate_id=f"{kind}:{item['id']}",
        kind=kind,
        source_query=source_query,
        title=item["title"],
        url=item["html_url"],
        repo_full_name=item["repository_url"].rsplit("/repos/", 1)[-1],
        author=item.get("user", {}).get("login", ""),
        created_at=item["created_at"],
        updated_at=item["updated_at"],
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
    return Candidate(
        candidate_id=f"repo:{item['nameWithOwner']}",
        kind="skill",
        source_query=source_query,
        title=item["nameWithOwner"],
        url=item["url"],
        repo_full_name=item["nameWithOwner"],
        author=item.get("owner", {}).get("login", ""),
        created_at=item["createdAt"],
        updated_at=item["updatedAt"],
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
