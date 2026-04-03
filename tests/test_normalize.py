from github_daily_radar.normalize.candidates import candidate_from_issue_search, candidate_from_repo_search


def test_candidate_from_repo_search():
    item = {
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

    candidate = candidate_from_repo_search(item=item, source_query="topic:agent")

    assert candidate.kind == "project"
    assert candidate.repo_full_name == "owner/repo"
    assert candidate.metrics.stars == 100


def test_candidate_from_issue_search():
    item = {
        "id": 123,
        "title": "Proposal: new idea",
        "html_url": "https://github.com/owner/repo/issues/1",
        "repository_url": "https://api.github.com/repos/owner/repo",
        "user": {"login": "author"},
        "created_at": "2026-04-01T00:00:00Z",
        "updated_at": "2026-04-02T00:00:00Z",
        "body": "details",
        "labels": [{"name": "proposal"}],
        "comments": 10,
    }

    candidate = candidate_from_issue_search(item=item, source_query="proposal")

    assert candidate.kind == "issue"
    assert candidate.repo_full_name == "owner/repo"
    assert candidate.metrics.comments == 10
