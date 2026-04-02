import argparse
from datetime import datetime, timezone
from pathlib import Path

from github_daily_radar.client import BudgetTracker, GitHubClient
from github_daily_radar.collectors.discussions import DiscussionCollector
from github_daily_radar.collectors.issues_prs import IssuesPrsCollector
from github_daily_radar.collectors.repos import RepoCollector
from github_daily_radar.collectors.skills import SkillCollector
from github_daily_radar.config import Settings
from github_daily_radar.publish.feishu import build_cards, send_cards
from github_daily_radar.scoring.dedupe import should_reenter
from github_daily_radar.state.store import StateStore
from github_daily_radar.summarize.digest import group_digest_items
from github_daily_radar.summarize.llm import EditorialLLM


def should_publish(*, dry_run: bool, alert_only: bool = False) -> bool:
    return not dry_run and not alert_only


def should_update_state(*, dry_run: bool, alert_only: bool = False) -> bool:
    return not dry_run and not alert_only


def run_pipeline(settings: Settings, alert_only: bool = False) -> dict:
    if alert_only:
        return {"mode": "alert-only"}

    today = datetime.now(timezone.utc).date()
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

    collectors = [
        RepoCollector(
            client=client,
            queries=[
                "(topic:agent OR topic:workflow OR topic:automation) pushed:>2026-03-26 sort:updated-desc",
                "(topic:llm OR topic:devtools OR topic:browser-use) pushed:>2026-03-26 sort:updated-desc",
            ],
        ),
        SkillCollector(
            client=client,
            queries=[
                "(topic:agent OR topic:prompt OR topic:workflow) in:name,description,readme workflow prompt skill pushed:>2026-03-19 sort:stars-desc",
            ],
        ),
        DiscussionCollector(client=client),
        IssuesPrsCollector(client=client),
    ]

    candidates = []
    for collector in collectors:
        candidates.extend(collector.collect())

    filtered = []
    for candidate in candidates:
        if state.is_in_cooldown(candidate.candidate_id, settings.cooldown_days, today):
            if should_reenter(candidate):
                filtered.append(candidate)
        else:
            filtered.append(candidate)

    llm = EditorialLLM(api_key=settings.qwen_api_key, model=settings.default_model)
    editorial = llm.rank_and_summarize(
        [
            {"title": item.title, "kind": item.kind, "url": item.url}
            for item in filtered[: settings.llm_max_candidates]
        ]
    )

    sections = group_digest_items(
        [{"kind": item.kind, "title": item.title, "url": item.url} for item in filtered]
    )
    cards = build_cards(
        title="GitHub Daily Radar",
        sections=sections,
        metadata={"count": len(filtered), "editorial": len(editorial)},
    )

    if should_publish(dry_run=settings.dry_run, alert_only=alert_only):
        send_cards(webhook_url=settings.feishu_webhook_url, cards=cards)

    if should_update_state(dry_run=settings.dry_run, alert_only=alert_only):
        state.write_daily_state(today.isoformat(), {"cards": cards, "count": len(filtered)})
        state.record_published(today, filtered)

    return {"cards": cards, "count": len(filtered)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alert-only", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()
    run_pipeline(settings=settings, alert_only=args.alert_only)


if __name__ == "__main__":
    main()
