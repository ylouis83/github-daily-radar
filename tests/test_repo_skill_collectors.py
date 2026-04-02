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
    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def search_code(self, query, per_page=20):
            self.calls.append(("code", query))
            return {
                "items": [
                    {
                        "name": "SKILL.md",
                        "path": "skills/SKILL.md",
                        "repository": {
                            "full_name": "owner/shared-skill",
                            "html_url": "https://github.com/owner/shared-skill",
                            "owner": {"login": "owner"},
                            "created_at": "2026-04-01T00:00:00Z",
                            "updated_at": "2026-04-02T00:00:00Z",
                            "description": "agent workflow prompts",
                            "topics": ["agent"],
                            "stargazers_count": 50,
                            "forks_count": 2,
                        },
                    }
                ]
            }

        def search_repositories(self, query, per_page=20, *, sort=None, order=None):
            self.calls.append(("repo", query))
            return {
                "items": [
                    {
                        "full_name": "owner/shared-skill",
                        "html_url": "https://github.com/owner/shared-skill",
                        "owner": {"login": "owner"},
                        "created_at": "2026-04-01T00:00:00Z",
                        "updated_at": "2026-04-02T00:00:00Z",
                        "description": "agent workflow prompts",
                        "topics": ["agent"],
                        "stargazers_count": 50,
                        "forks_count": 2,
                    }
                ]
            }

        def graphql(self, query, variables=None, cost=1):
            self.calls.append(("graphql", query))
            assert 'repository(owner: "owner", name: "seed-skill")' in query
            return {
                "data": {
                    "seed_skill_0": {
                        "nameWithOwner": "owner/seed-skill",
                        "url": "https://github.com/owner/seed-skill",
                        "description": "seed skill repo",
                        "createdAt": "2026-03-20T00:00:00Z",
                        "updatedAt": "2026-04-02T00:00:00Z",
                        "pushedAt": "2026-04-02T00:00:00Z",
                        "stargazerCount": 20,
                        "forkCount": 3,
                        "repositoryTopics": {"nodes": [{"topic": {"name": "agent"}}]},
                        "releases": {"nodes": [{"publishedAt": "2026-04-01T00:00:00Z", "name": "v1.0"}]},
                        "owner": {"login": "owner"},
                    }
                }
            }

    client = FakeClient()
    collector = SkillCollector(
        client=client,
        code_queries=["filename:SKILL.md path:skills"],
        repo_queries=["(topic:agent OR topic:prompt) in:name,description,readme pushed:>2026-03-19"],
        seed_repos=["owner/seed-skill"],
    )

    items = collector.collect()

    assert client.calls[0][0] == "code"
    assert client.calls[1][0] == "repo"
    assert client.calls[2][0] == "graphql"
    assert len(items) == 2
    assert {item.repo_full_name for item in items} == {"owner/shared-skill", "owner/seed-skill"}
    assert all(item.kind == "skill" for item in items)
