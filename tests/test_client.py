import respx
from httpx import Response

from github_daily_radar.client import BudgetTracker, GitHubClient


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
