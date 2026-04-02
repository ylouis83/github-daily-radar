from github_daily_radar.collectors.skills import SkillCollector


class FakeClient:
    def __init__(self, code_items: list[dict] | None = None, repo_items: list[dict] | None = None) -> None:
        self.code_items = code_items or []
        self.repo_items = repo_items or []
        self.calls: list[tuple[str, str]] = []

    def search_code(self, query, per_page=20, *, sort=None, order=None):
        self.calls.append(("code", query))
        return {"items": list(self.code_items)}

    def search_repositories(self, query, per_page=20, *, sort=None, order=None):
        self.calls.append(("repo", query))
        return {"items": list(self.repo_items)}


def test_skill_collector_keeps_low_star_skill_shape_and_big_project():
    client = FakeClient(
        code_items=[
            {
                "name": "SKILL.md",
                "path": "skills/SKILL.md",
                "repository": {
                    "full_name": "owner/skill-pack",
                    "html_url": "https://github.com/owner/skill-pack",
                    "owner": {"login": "owner"},
                    "description": "prompt pack",
                    "topics": ["agent"],
                    "stargazers_count": 2,
                    "forks_count": 1,
                },
            },
            {
                "name": "README.md",
                "path": "notes/README.md",
                "repository": {
                    "full_name": "owner/noise",
                    "html_url": "https://github.com/owner/noise",
                    "owner": {"login": "owner"},
                    "description": "misc notes",
                    "topics": [],
                    "stargazers_count": 1,
                    "forks_count": 0,
                },
            },
        ],
        repo_items=[
            {
                "full_name": "owner/big-project",
                "html_url": "https://github.com/owner/big-project",
                "owner": {"login": "owner"},
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-02T00:00:00Z",
                "description": "agent platform",
                "topics": ["agent"],
                "stargazers_count": 250,
                "forks_count": 40,
            },
            {
                "full_name": "owner/tiny-noise",
                "html_url": "https://github.com/owner/tiny-noise",
                "owner": {"login": "owner"},
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-02T00:00:00Z",
                "description": "misc",
                "topics": ["agent"],
                "stargazers_count": 4,
                "forks_count": 0,
            },
        ],
    )

    collector = SkillCollector(
        client=client,
        code_queries=["filename:SKILL.md path:skills"],
        repo_queries=["cursor rules AI in:name,description"],
        seed_repos=[],
        skill_min_stars=3,
        project_min_stars=20,
        skill_shape_floor=2,
        top_n=10,
    )

    items = collector.collect()

    assert {item.repo_full_name for item in items} == {"owner/skill-pack", "owner/big-project"}
    assert {item.kind for item in items} == {"skill", "project"}
    assert all(item.repo_full_name != "owner/noise" for item in items)
    assert all(item.repo_full_name != "owner/tiny-noise" for item in items)


def test_skill_collector_rejects_low_star_noise_without_skill_shape():
    client = FakeClient(
        code_items=[
            {
                "name": "README.md",
                "path": "docs/README.md",
                "repository": {
                    "full_name": "owner/noise",
                    "html_url": "https://github.com/owner/noise",
                    "owner": {"login": "owner"},
                    "description": "misc notes",
                    "topics": [],
                    "stargazers_count": 1,
                    "forks_count": 0,
                },
            }
        ],
        repo_items=[
            {
                "full_name": "owner/noise-repo",
                "html_url": "https://github.com/owner/noise-repo",
                "owner": {"login": "owner"},
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-02T00:00:00Z",
                "description": "misc",
                "topics": ["agent"],
                "stargazers_count": 2,
                "forks_count": 0,
            }
        ],
    )

    collector = SkillCollector(
        client=client,
        code_queries=["filename:README.md"],
        repo_queries=["agent in:name,description"],
        seed_repos=[],
        skill_min_stars=3,
        project_min_stars=20,
        skill_shape_floor=2,
        top_n=10,
    )

    assert collector.collect() == []


def test_skill_collector_respects_top_n_and_dedupes_best_repo():
    client = FakeClient(
        code_items=[
            {
                "name": "SKILL.md",
                "path": "skills/SKILL.md",
                "repository": {
                    "full_name": "owner/shared-skill",
                    "html_url": "https://github.com/owner/shared-skill",
                    "owner": {"login": "owner"},
                    "description": "agent workflow prompts",
                    "topics": ["agent"],
                    "stargazers_count": 5,
                    "forks_count": 1,
                },
            }
        ],
        repo_items=[
            {
                "full_name": "owner/shared-skill",
                "html_url": "https://github.com/owner/shared-skill",
                "owner": {"login": "owner"},
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-02T00:00:00Z",
                "description": "agent workflow prompts",
                "topics": ["agent"],
                "stargazers_count": 5,
                "forks_count": 1,
            },
            {
                "full_name": "owner/big-project",
                "html_url": "https://github.com/owner/big-project",
                "owner": {"login": "owner"},
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-02T00:00:00Z",
                "description": "agent platform",
                "topics": ["agent"],
                "stargazers_count": 180,
                "forks_count": 20,
            },
            {
                "full_name": "owner/medium-project",
                "html_url": "https://github.com/owner/medium-project",
                "owner": {"login": "owner"},
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-02T00:00:00Z",
                "description": "agent infra",
                "topics": ["agent"],
                "stargazers_count": 90,
                "forks_count": 10,
            },
        ],
    )

    collector = SkillCollector(
        client=client,
        code_queries=["filename:SKILL.md path:skills"],
        repo_queries=["agent in:name,description"],
        seed_repos=[],
        skill_min_stars=3,
        project_min_stars=20,
        skill_shape_floor=2,
        top_n=2,
    )

    items = collector.collect()

    assert len(items) == 2
    assert {item.repo_full_name for item in items} == {"owner/shared-skill", "owner/big-project"}
