from github_daily_radar.collectors.skills import SkillCollector


class FakeClient:
    def __init__(
        self,
        code_items: list[dict] | None = None,
        repo_items: list[dict] | None = None,
        graphql_data: dict | None = None,
    ) -> None:
        self.code_items = code_items or []
        self.repo_items = repo_items or []
        self.graphql_data = graphql_data or {"data": {}}
        self.calls: list[tuple[str, str]] = []

    def search_code(self, query, per_page=20, *, sort=None, order=None):
        self.calls.append(("code", query))
        return {"items": list(self.code_items)}

    def search_repositories(self, query, per_page=20, *, sort=None, order=None):
        self.calls.append(("repo", query))
        return {"items": list(self.repo_items)}

    def graphql(self, query, variables=None, cost=1):
        self.calls.append(("graphql", query))
        return self.graphql_data


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
    seed_hit = next(item for item in items if item.repo_full_name == "punkpeye/awesome-mcp-servers")
    assert seed_hit.kind == "skill"


def test_skill_collector_filters_known_noise_repos():
    client = FakeClient(
        repo_items=[
            {
                "full_name": "liyupi/ai-guide",
                "html_url": "https://github.com/liyupi/ai-guide",
                "owner": {"login": "liyupi"},
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-02T00:00:00Z",
                "description": "AI guide and tutorial collection",
                "topics": ["agent"],
                "stargazers_count": 12000,
                "forks_count": 1000,
            },
            {
                "full_name": "AgnosticUI/agnosticui",
                "html_url": "https://github.com/AgnosticUI/agnosticui",
                "owner": {"login": "AgnosticUI"},
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-02T00:00:00Z",
                "description": "A CLI-based UI component library for agent-driven workflows",
                "topics": ["agent"],
                "stargazers_count": 796,
                "forks_count": 50,
            },
            {
                "full_name": "refly-ai/refly",
                "html_url": "https://github.com/refly-ai/refly",
                "owner": {"login": "refly-ai"},
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-02T00:00:00Z",
                "description": "The first open-source agent skills builder",
                "topics": ["agent"],
                "stargazers_count": 7217,
                "forks_count": 300,
            },
        ],
    )

    collector = SkillCollector(
        client=client,
        code_queries=[],
        repo_queries=["claude skills agent prompt in:name,description"],
        seed_repos=[],
        skill_min_stars=80,
        project_min_stars=120,
        skill_shape_floor=3,
        top_n=20,
    )

    items = collector.collect()

    assert [item.repo_full_name for item in items] == ["refly-ai/refly"]


def test_skill_collector_prefers_hot_skills_by_growth_then_stars():
    client = FakeClient(
        repo_items=[
            {
                "full_name": "owner/stable-skill",
                "html_url": "https://github.com/owner/stable-skill",
                "owner": {"login": "owner"},
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-02T00:00:00Z",
                "description": "agent workflow prompts",
                "topics": ["agent"],
                "stargazers_count": 4000,
                "forks_count": 40,
            },
            {
                "full_name": "owner/hot-skill",
                "html_url": "https://github.com/owner/hot-skill",
                "owner": {"login": "owner"},
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-02T00:00:00Z",
                "description": "agent workflow prompts",
                "topics": ["agent"],
                "stargazers_count": 2600,
                "forks_count": 35,
            },
        ],
    )

    collector = SkillCollector(
        client=client,
        code_queries=[],
        repo_queries=["agent workflow prompt in:name,description"],
        seed_repos=[],
        skill_min_stars=80,
        project_min_stars=120,
        skill_shape_floor=3,
        top_n=20,
        previous_stars_by_repo={
            "owner/stable-skill": 3950,
            "owner/hot-skill": 900,
        },
    )

    items = collector.collect()

    assert [item.repo_full_name for item in items[:2]] == ["owner/hot-skill", "owner/stable-skill"]
    assert items[0].metrics.star_growth_7d == 1700
    assert items[1].metrics.star_growth_7d == 50


def test_skill_collector_super_growth_skill_can_bypass_recent_cooldown():
    client = FakeClient(
        repo_items=[
            {
                "full_name": "owner/breakout-skill",
                "html_url": "https://github.com/owner/breakout-skill",
                "owner": {"login": "owner"},
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-02T00:00:00Z",
                "description": "agent workflow prompts",
                "topics": ["agent"],
                "stargazers_count": 2600,
                "forks_count": 35,
            },
        ],
    )

    collector = SkillCollector(
        client=client,
        code_queries=[],
        repo_queries=["agent workflow prompt in:name,description"],
        seed_repos=[],
        skill_min_stars=80,
        project_min_stars=120,
        skill_shape_floor=3,
        top_n=20,
        cooldown_repo_ids={"owner/breakout-skill", "skill:owner/breakout-skill"},
        previous_stars_by_repo={"owner/breakout-skill": 1200},
    )

    items = collector.collect()

    assert len(items) == 1
    assert items[0].repo_full_name == "owner/breakout-skill"
    assert items[0].metrics.star_growth_7d == 1400
