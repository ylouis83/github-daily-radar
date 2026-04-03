import respx
from httpx import Response

from github_daily_radar.client import BudgetTracker, GitHubClient, OSSInsightClient


@respx.mock
def test_search_repositories_calls_api():
    route = respx.get("https://api.github.com/search/repositories").mock(
        return_value=Response(200, json={"items": [{"full_name": "owner/repo"}]})
    )

    client = GitHubClient(
        token="ghs_test",
        budget=BudgetTracker(total_budget=10, search_budget=2, graphql_budget=10),
        search_requests_per_minute=100,
    )

    payload = client.search_repositories("topic:agent")

    assert route.called is True
    assert payload["items"][0]["full_name"] == "owner/repo"


@respx.mock
def test_search_code_calls_api():
    route = respx.get("https://api.github.com/search/code").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "name": "SKILL.md",
                        "path": "skills/SKILL.md",
                        "repository": {
                            "full_name": "owner/skill-pack",
                            "html_url": "https://github.com/owner/skill-pack",
                            "owner": {"login": "owner"},
                            "created_at": "2026-04-01T00:00:00Z",
                            "updated_at": "2026-04-02T00:00:00Z",
                            "description": "skill pack",
                            "topics": ["agent"],
                            "stargazers_count": 10,
                            "forks_count": 1,
                        },
                    }
                ]
            },
        )
    )

    client = GitHubClient(
        token="ghs_test",
        budget=BudgetTracker(total_budget=10, search_budget=2, graphql_budget=10),
        search_requests_per_minute=100,
    )

    payload = client.search_code("filename:SKILL.md")

    assert route.called is True
    assert payload["items"][0]["repository"]["full_name"] == "owner/skill-pack"


@respx.mock
def test_search_code_does_not_retry_on_429():
    route = respx.get("https://api.github.com/search/code").mock(
        return_value=Response(429, json={"message": "rate limited"})
    )

    client = GitHubClient(
        token="ghs_test",
        budget=BudgetTracker(total_budget=10, search_budget=2, graphql_budget=10),
        search_requests_per_minute=100,
        code_search_requests_per_minute=100,
    )

    try:
        client.search_code("filename:SKILL.md")
    except Exception:
        pass

    assert len(route.calls) == 1


@respx.mock
def test_search_budget_exhausted_raises():
    respx.get("https://api.github.com/search/issues").mock(return_value=Response(200, json={"items": []}))

    client = GitHubClient(
        token="ghs_test",
        budget=BudgetTracker(total_budget=10, search_budget=1, graphql_budget=10),
        search_requests_per_minute=100,
    )

    client.search_issues("proposal")

    try:
        client.search_issues("proposal")
    except RuntimeError as exc:
        assert "search budget exhausted" in str(exc)
    else:
        raise AssertionError("Expected search budget exhaustion")


@respx.mock
def test_graphql_budget_exhausted_raises():
    respx.post("https://api.github.com/graphql").mock(return_value=Response(200, json={"data": {}}))

    client = GitHubClient(
        token="ghs_test",
        budget=BudgetTracker(total_budget=10, search_budget=10, graphql_budget=3),
        search_requests_per_minute=100,
    )

    client.graphql("query { viewer { login } }", cost=2)

    try:
        client.graphql("query { viewer { login } }", cost=2)
    except RuntimeError as exc:
        assert "graphql budget exhausted" in str(exc)
    else:
        raise AssertionError("Expected graphql budget exhaustion")


@respx.mock
def test_ossinsight_trending_endpoint_calls_api():
    route = respx.get("https://api.ossinsight.io/v1/trends/repos/").mock(
        return_value=Response(200, json={"data": {"rows": [{"repo_name": "owner/repo"}]}})
    )

    client = OSSInsightClient()

    payload = client.list_trending_repos(period="past_24_hours", language="All")

    assert route.called is True
    assert payload["data"]["rows"][0]["repo_name"] == "owner/repo"


@respx.mock
def test_ossinsight_collection_endpoint_calls_api():
    route = respx.get("https://api.ossinsight.io/v1/collections/10010/ranking_by_stars/").mock(
        return_value=Response(200, json={"data": {"rows": [{"repo_name": "owner/repo"}]}})
    )

    client = OSSInsightClient()

    payload = client.collection_ranking_by_stars(10010, period="past_28_days")

    assert route.called is True
    assert payload["data"]["rows"][0]["repo_name"] == "owner/repo"
