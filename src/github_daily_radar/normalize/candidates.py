from github_daily_radar.models import Candidate, CandidateMetrics


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


def candidate_from_issue_search(*, item: dict, source_query: str) -> Candidate:
    return Candidate(
        candidate_id=f"issue:{item['id']}",
        kind="issue",
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
