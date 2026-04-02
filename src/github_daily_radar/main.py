import argparse
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from github_daily_radar.client import BudgetTracker, GitHubClient
from github_daily_radar.discovery import (
    build_discussion_queries,
    build_issue_pr_queries,
    build_repo_queries,
    build_skill_code_queries,
    build_skill_repo_queries,
    load_seed_repos,
    load_skill_seed_repos,
)
from github_daily_radar.collectors.discussions import DiscussionCollector
from github_daily_radar.collectors.issues_prs import IssuesPrsCollector
from github_daily_radar.collectors.repos import RepoCollector
from github_daily_radar.collectors.skills import SkillCollector
from github_daily_radar.config import Settings
from github_daily_radar.publish.feishu import build_alert_cards, build_digest_cards, send_cards
from github_daily_radar.scoring.dedupe import should_reenter
from github_daily_radar.state.store import StateStore
from github_daily_radar.summarize.digest import (
    build_display_items,
    build_card_sections,
    score_candidate,
    split_a_b,
)
from github_daily_radar.summarize.llm import EditorialLLM


def should_publish(*, dry_run: bool, alert_only: bool = False) -> bool:
    return not dry_run and not alert_only


def should_update_state(*, dry_run: bool, alert_only: bool = False) -> bool:
    return not dry_run and not alert_only


def product_today(*, timezone_name: str, now: datetime | None = None) -> date:
    moment = now or datetime.now(timezone.utc)
    return moment.astimezone(ZoneInfo(timezone_name)).date()


def run_pipeline(settings: Settings, alert_only: bool = False) -> dict:
    if alert_only:
        send_cards(
            webhook_url=settings.feishu_webhook_url,
            cards=build_alert_cards(
                title="GitHub Daily Radar Alert",
                message=(
                    "GitHub Daily Radar entered alert-only mode. "
                    "Check the latest GitHub Actions run for the failure details."
                ),
                metadata={"mode": "alert-only"},
            ),
        )
        return {"mode": "alert-only"}

    run_started_at = datetime.now(timezone.utc)
    today = product_today(timezone_name=settings.timezone, now=run_started_at)
    state = StateStore(base_dir=Path("artifacts/state"))

    client = GitHubClient(
        token=settings.github_auth_token,
        budget=BudgetTracker(
            total_budget=settings.api_total_budget,
            search_budget=settings.api_search_budget,
            graphql_budget=settings.api_graphql_budget,
        ),
        search_requests_per_minute=settings.search_requests_per_minute,
    )

    seed_repos = load_seed_repos()
    skill_seed_repos = load_skill_seed_repos()
    collectors = [
        RepoCollector(client=client, queries=build_repo_queries(now=run_started_at, days_back=7)),
        SkillCollector(
            client=client,
            code_queries=build_skill_code_queries(),
            repo_queries=build_skill_repo_queries(days_back=30),
            seed_repos=skill_seed_repos,
        ),
        DiscussionCollector(
            client=client,
            queries=build_discussion_queries(seed_repos=seed_repos, now=run_started_at, days_back=14),
        ),
        IssuesPrsCollector(
            client=client,
            queries=build_issue_pr_queries(seed_repos=seed_repos, now=run_started_at, days_back=14),
        ),
    ]

    candidates = []
    collector_errors: list[dict[str, str]] = []
    for collector in collectors:
        try:
            candidates.extend(collector.collect())
        except Exception as exc:  # noqa: BLE001 - keep one collector failure from stopping the rest
            collector_errors.append({"collector": getattr(collector, "name", "collector"), "error": str(exc)})

    state.record_seen(today, candidates)

    filtered = []
    for candidate in candidates:
        if state.is_in_cooldown(candidate.candidate_id, settings.cooldown_days, today):
            if should_reenter(candidate):
                filtered.append(candidate)
        else:
            filtered.append(candidate)

    ranked_candidates = sorted(filtered, key=score_candidate, reverse=True)
    llm = EditorialLLM(api_key=settings.qwen_api_key, model=settings.default_model)
    editorial = llm.rank_and_summarize(
        [
            {
                "title": item.title,
                "kind": item.kind,
                "url": item.url,
                "repo": item.repo_full_name,
                "signals": {
                    "stars": item.metrics.stars,
                    "forks": item.metrics.forks,
                    "comments": item.metrics.comments,
                    "reactions": item.metrics.reactions,
                },
                "excerpt": item.body_excerpt[:200],
            }
            for item in ranked_candidates[: settings.llm_max_candidates]
        ]
    )

    metadata = {
        "count": len(filtered),
        "editorial": len(editorial),
    }
    if collector_errors:
        metadata["collector_errors"] = len(collector_errors)
        metadata["coverage_note"] = "Reduced coverage due to collector failure(s)."
    api_usage = client._budget.snapshot()
    metadata["api_usage"] = api_usage
    display_items = build_display_items(filtered, editorial)
    a_items, b_items = split_a_b(display_items, a_max=10, b_max=10)
    published_items = a_items + b_items
    filtered_kind_counts = Counter(item.kind for item in filtered)
    published_kind_counts = Counter(item["kind"] for item in published_items)
    metadata["a_count"] = len(a_items)
    metadata["b_count"] = len(b_items)
    metadata["filtered_kind_counts"] = dict(filtered_kind_counts)
    metadata["published_kind_counts"] = dict(published_kind_counts)
    sections_a = build_card_sections(a_items, variant="A", metadata=metadata)
    sections_b = build_card_sections(b_items, variant="B", metadata=metadata)
    cards = build_digest_cards(
        title="GitHub Daily Radar",
        bundles=[
            {"label": "A 精编版", "sections": sections_a},
            {"label": "B 保留版", "sections": sections_b},
        ],
        metadata=None,
    )

    if should_publish(dry_run=settings.dry_run, alert_only=alert_only):
        send_cards(webhook_url=settings.feishu_webhook_url, cards=cards)

    if should_update_state(dry_run=settings.dry_run, alert_only=alert_only):
        state.write_daily_state(
            today.isoformat(),
            {
                "cards": cards,
                "count": len(filtered),
                "selected_count": len(published_items),
                "summary": metadata,
            },
        )
        state.record_run_summary(
            today,
            {
                "candidate_count": len(candidates),
                "selected_count": len(published_items),
                "filtered_kind_counts": dict(filtered_kind_counts),
                "published_kind_counts": dict(published_kind_counts),
                "collector_errors": collector_errors,
                "api_usage": api_usage,
                "timezone": settings.timezone,
            },
        )
        state.record_published(today, published_items)

    return {"cards": cards, "count": len(filtered), "summary": metadata}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alert-only", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()
    run_pipeline(settings=settings, alert_only=args.alert_only)


if __name__ == "__main__":
    main()
