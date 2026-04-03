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


def test_skill_collector_keeps_high_star_skill_and_big_project():
    """High-star skill (>=80 with shape) and big project (>=120) both pass."""
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
                    "stargazers_count": 100,
                    "forks_count": 10,
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
        ],
    )

    collector = SkillCollector(
        client=client,
        code_queries=["filename:SKILL.md path:skills"],
        repo_queries=["cursor rules AI in:name,description"],
        seed_repos=[],
        skill_min_stars=80,
        project_min_stars=120,
        skill_shape_floor=3,
        top_n=20,
    )

    items = collector.collect()

    assert {item.repo_full_name for item in items} == {"owner/skill-pack", "owner/big-project"}
    assert {item.kind for item in items} == {"skill", "project"}


def test_skill_collector_rejects_below_absolute_floor():
    """Repos with <10 stars are always rejected, even with high shape score."""
    client = FakeClient(
        code_items=[
            {
                "name": "SKILL.md",
                "path": "skills/SKILL.md",
                "repository": {
                    "full_name": "owner/tiny-skill",
                    "html_url": "https://github.com/owner/tiny-skill",
                    "owner": {"login": "owner"},
                    "description": "prompt agent workflow",
                    "topics": ["agent"],
                    "stargazers_count": 2,
                    "forks_count": 1,
                },
            },
            {
                "name": "SKILL.md",
                "path": "skills/SKILL.md",
                "repository": {
                    "full_name": "owner/zero-star",
                    "html_url": "https://github.com/owner/zero-star",
                    "owner": {"login": "owner"},
                    "description": "agent skill prompt rules",
                    "topics": [],
                    "stargazers_count": 0,
                    "forks_count": 0,
                },
            },
        ],
    )

    collector = SkillCollector(
        client=client,
        code_queries=["filename:SKILL.md path:skills"],
        repo_queries=[],
        seed_repos=[],
        skill_min_stars=80,
        project_min_stars=120,
        skill_shape_floor=3,
        top_n=20,
    )

    assert collector.collect() == []


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
                    "stargazers_count": 15,
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
                "stargazers_count": 20,
                "forks_count": 0,
            }
        ],
    )

    collector = SkillCollector(
        client=client,
        code_queries=["filename:README.md"],
        repo_queries=["agent in:name,description"],
        seed_repos=[],
        skill_min_stars=80,
        project_min_stars=120,
        skill_shape_floor=3,
        top_n=20,
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
                    "stargazers_count": 90,
                    "forks_count": 8,
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
                "stargazers_count": 90,
                "forks_count": 8,
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
                "description": "misc",
                "topics": [],
                "stargazers_count": 30,
                "forks_count": 2,
            },
        ],
    )

    collector = SkillCollector(
        client=client,
        code_queries=["filename:SKILL.md path:skills"],
        repo_queries=["agent in:name,description"],
        seed_repos=[],
        skill_min_stars=80,
        project_min_stars=120,
        skill_shape_floor=3,
        top_n=2,
    )

    items = collector.collect()

    assert len(items) == 2
    assert {item.repo_full_name for item in items} == {"owner/shared-skill", "owner/big-project"}


def test_skill_collector_cooldown_excludes_recent_published():
    """Repos in cooldown_repo_ids are excluded even if they pass all other gates."""
    client = FakeClient(
        code_items=[
            {
                "name": "SKILL.md",
                "path": "skills/SKILL.md",
                "repository": {
                    "full_name": "owner/cool-skill",
                    "html_url": "https://github.com/owner/cool-skill",
                    "owner": {"login": "owner"},
                    "description": "agent workflow tool",
                    "topics": ["agent"],
                    "stargazers_count": 200,
                    "forks_count": 20,
                },
            },
            {
                "name": "SKILL.md",
                "path": "skills/SKILL.md",
                "repository": {
                    "full_name": "owner/fresh-skill",
                    "html_url": "https://github.com/owner/fresh-skill",
                    "owner": {"login": "owner"},
                    "description": "prompt rules",
                    "topics": ["agent"],
                    "stargazers_count": 150,
                    "forks_count": 10,
                },
            },
        ],
    )

    collector = SkillCollector(
        client=client,
        code_queries=["filename:SKILL.md path:skills"],
        repo_queries=[],
        seed_repos=[],
        skill_min_stars=80,
        project_min_stars=120,
        skill_shape_floor=3,
        top_n=20,
        cooldown_repo_ids={"owner/cool-skill", "skill:owner/cool-skill"},
    )

    items = collector.collect()

    assert len(items) == 1
    assert items[0].repo_full_name == "owner/fresh-skill"


def test_skill_collector_seed_repos_no_longer_permanently_excluded():
    """seed_repos are NOT permanently excluded anymore — they can appear in results."""
    client = FakeClient(
        repo_items=[
            {
                "full_name": "punkpeye/awesome-mcp-servers",
                "html_url": "https://github.com/punkpeye/awesome-mcp-servers",
                "owner": {"login": "punkpeye"},
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-02T00:00:00Z",
                "description": "MCP server collection",
                "topics": ["mcp"],
                "stargazers_count": 40000,
                "forks_count": 5000,
            },
        ],
    )

    collector = SkillCollector(
        client=client,
        code_queries=[],
        repo_queries=["mcp server tool in:name,description"],
        seed_repos=["punkpeye/awesome-mcp-servers"],  # was excluded before
        skill_min_stars=80,
        project_min_stars=120,
        skill_shape_floor=3,
        top_n=20,
    )

    items = collector.collect()
    assert any(item.repo_full_name == "punkpeye/awesome-mcp-servers" for item in items)
