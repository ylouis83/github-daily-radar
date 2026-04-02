import respx
from httpx import Response

from github_daily_radar.client import BudgetTracker, GitHubClient
from github_daily_radar.collectors.repos import RepoCollector
from github_daily_radar.collectors.skills import SkillCollector


@respx.mock
def test_repo_collector_collects_candidates():
    respx.get("https://api.github.com/search/repositories").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
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
                ]
            },
        )
    )

    client = GitHubClient("ghs_test", BudgetTracker(total_budget=10, search_budget=5, graphql_budget=10))
    collector = RepoCollector(
        client=client,
        queries=["(topic:agent OR topic:workflow) pushed:>2026-03-26 sort:updated-desc"],
    )

    items = collector.collect()

    assert items[0].kind == "project"


@respx.mock
def test_skill_collector_collects_candidates():
    respx.get("https://api.github.com/search/repositories").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "full_name": "owner/skills-repo",
                        "html_url": "https://github.com/owner/skills-repo",
                        "owner": {"login": "owner"},
                        "created_at": "2026-04-01T00:00:00Z",
                        "updated_at": "2026-04-02T00:00:00Z",
                        "description": "agent workflow prompts",
                        "topics": ["agent"],
                        "stargazers_count": 50,
                        "forks_count": 2,
                    }
                ]
            },
        )
    )

    client = GitHubClient("ghs_test", BudgetTracker(total_budget=10, search_budget=5, graphql_budget=10))
    collector = SkillCollector(
        client=client,
        queries=[
            "(topic:agent OR topic:prompt) in:name,description,readme workflow prompt skill pushed:>2026-03-19 sort:stars-desc"
        ],
    )

    items = collector.collect()

    assert items[0].kind == "skill"
