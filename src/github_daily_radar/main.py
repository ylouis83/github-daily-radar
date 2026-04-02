import argparse
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from github_daily_radar.client import BudgetTracker, GitHubClient
from github_daily_radar.collectors.discussions import DiscussionCollector
from github_daily_radar.collectors.issues_prs import IssuesPrsCollector
from github_daily_radar.collectors.repos import RepoCollector
from github_daily_radar.collectors.skills import SkillCollector
from github_daily_radar.config import Settings
from github_daily_radar.models import Candidate
from github_daily_radar.publish.feishu import build_alert_cards, build_cards, send_cards
from github_daily_radar.scoring.dedupe import should_reenter
from github_daily_radar.state.store import StateStore
from github_daily_radar.summarize.digest import group_digest_items
from github_daily_radar.summarize.llm import EditorialLLM


def should_publish(*, dry_run: bool, alert_only: bool = False) -> bool:
    return not dry_run and not alert_only


def should_update_state(*, dry_run: bool, alert_only: bool = False) -> bool:
    return not dry_run and not alert_only


def product_today(*, timezone_name: str, now: datetime | None = None) -> date:
    moment = now or datetime.now(timezone.utc)
    return moment.astimezone(ZoneInfo(timezone_name)).date()


def _fallback_display_item(candidate: Candidate) -> dict:
    summary = candidate.body_excerpt.strip()
    if not summary:
        summary = (
            f"Signals: stars {candidate.metrics.stars}, "
            f"forks {candidate.metrics.forks}, comments {candidate.metrics.comments}"
        )
    return {
        "kind": candidate.kind,
        "title": candidate.title,
        "url": candidate.url,
        "summary": summary[:160],
    }


def _merge_editorial(candidates: list[Candidate], editorial: list[dict]) -> list[dict]:
    display_items = [_fallback_display_item(candidate) for candidate in candidates]
    if not editorial:
        return display_items

    editorial_by_url = {item.get("url"): item for item in editorial if item.get("url")}
    editorial_by_title = {item.get("title"): item for item in editorial if item.get("title")}

    merged: list[dict] = []
    for candidate, fallback in zip(candidates, display_items):
        merged_item = dict(fallback)
        editorial_item = editorial_by_url.get(candidate.url) or editorial_by_title.get(candidate.title)
        if editorial_item:
            merged_item["kind"] = editorial_item.get("kind", merged_item["kind"])
            merged_item["title"] = editorial_item.get("title", merged_item["title"])
            merged_item["url"] = editorial_item.get("url", merged_item["url"])
            merged_item["summary"] = (
                editorial_item.get("summary")
                or editorial_item.get("why_now")
                or merged_item["summary"]
            )
            if editorial_item.get("why_now"):
                merged_item["why_now"] = editorial_item["why_now"]
            rank = editorial_item.get("rank", editorial_item.get("editorial_rank"))
            if rank is not None:
                merged_item["editorial_rank"] = rank
            if editorial_item.get("section"):
                merged_item["section"] = editorial_item["section"]
        merged.append(merged_item)
    return merged


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

    today = product_today(timezone_name=settings.timezone)
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
    collector_errors: list[dict[str, str]] = []
    for collector in collectors:
        try:
            candidates.extend(collector.collect())
        except Exception as exc:  # noqa: BLE001 - keep one collector failure from stopping the rest
            collector_errors.append({"collector": getattr(collector, "name", "collector"), "error": str(exc)})

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

    digest_items = _merge_editorial(filtered, editorial)
    sections = group_digest_items(digest_items)
    metadata = {
        "count": len(filtered),
        "editorial": len(editorial),
    }
    if collector_errors:
        metadata["collector_errors"] = len(collector_errors)
        metadata["coverage_note"] = "Reduced coverage due to collector failure(s)."
    cards = build_cards(
        title="GitHub Daily Radar",
        sections=sections,
        metadata=metadata,
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
