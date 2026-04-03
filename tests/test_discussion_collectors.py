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
