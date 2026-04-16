from github_daily_radar.daily_brief import assemble_daily_brief
from github_daily_radar.models import BuilderSignal, ExternalTechCandidate


def test_assemble_daily_brief_promotes_repo_like_buzzing_item_to_github_track():
    github_items = [
        {
            "kind": "project",
            "title": "owner/repo",
            "url": "https://github.com/owner/repo",
            "repo_full_name": "owner/repo",
        }
    ]
    tech_candidates = [
        ExternalTechCandidate(
            source="showhn",
            title="owner/repo",
            url="https://github.com/owner/repo",
            summary="ship fast",
            score=220,
            comments=18,
            tags=["Developer Tools", "GitHub"],
            published_at="2026-04-16T00:00:00Z",
        )
    ]

    brief = assemble_daily_brief(
        github_items=github_items,
        tech_candidates=tech_candidates,
        builder_signals=[],
    )

    assert brief.github_radar[0]["external_heat"]["source"] == "showhn"
    assert brief.tech_pulse == []


def test_assemble_daily_brief_groups_builder_signals_by_section():
    signals = [
        BuilderSignal(
            source="x",
            section="x",
            title="Swyx",
            url="https://x.com/swyx/status/1",
            creator="Swyx",
            summary="Builder thread",
            score=45,
            published_at="2026-04-16T00:00:00Z",
        ),
        BuilderSignal(
            source="blog",
            section="blog",
            title="Builder essay",
            url="https://builder.example.com/post",
            creator="Builder",
            summary="Longform post",
            score=12,
            published_at="2026-04-16T00:00:00Z",
        ),
    ]

    brief = assemble_daily_brief(
        github_items=[],
        tech_candidates=[],
        builder_signals=signals,
    )

    assert [item["title"] for item in brief.builder_watch["x"]] == ["Swyx"]
    assert [item["title"] for item in brief.builder_watch["blog"]] == ["Builder essay"]
