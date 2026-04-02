import argparse
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from github_daily_radar.client import BudgetTracker, GitHubClient, OSSInsightClient
from github_daily_radar.discovery import (
    build_discussion_queries,
    build_issue_pr_queries,
    build_repo_queries,
    build_skill_code_queries,
    build_skill_repo_queries,
    cycle_queries,
    load_ossinsight_collection_name_keywords,
    load_ossinsight_collection_period,
    load_ossinsight_enabled,
    load_ossinsight_language,
    load_ossinsight_max_collection_ids,
    load_ossinsight_max_trending_items,
    load_ossinsight_trending_periods,
    load_output_daily_item_count_config,
    load_seed_repos,
    load_project_min_stars,
    load_skill_min_stars,
    load_skill_seed_repos,
    load_skill_shape_floor,
    load_skill_top_n,
    load_skill_per_repo_cap,
)
from github_daily_radar.collectors.ossinsight import OSSInsightCollector
from github_daily_radar.collectors.discussions import DiscussionCollector
from github_daily_radar.collectors.issues_prs import IssuesPrsCollector
from github_daily_radar.collectors.repos import RepoCollector
from github_daily_radar.collectors.skills import SkillCollector
from github_daily_radar.collectors.trending import TrendingCollector
from github_daily_radar.config import Settings
from github_daily_radar.publish.feishu import build_alert_cards, build_digest_card, send_cards
from github_daily_radar.scoring.dedupe import should_reenter
from github_daily_radar.state.store import StateStore
from github_daily_radar.summarize.digest import build_display_items, score_candidate, select_top_items
from github_daily_radar.summarize.llm import EditorialLLM

PUBLIC_CARD_METADATA_KEYS = frozenset(
    {
        "count",
        "editorial",
        "collector_errors",
        "collector_skips",
        "coverage_note",
        "api_usage",
        "item_count",
    }
)


def should_publish(*, dry_run: bool, alert_only: bool = False) -> bool:
    return not dry_run and not alert_only


def should_update_state(*, dry_run: bool, alert_only: bool = False) -> bool:
    return not dry_run and not alert_only


def product_today(*, timezone_name: str, now: datetime | None = None) -> date:
    moment = now or datetime.now(timezone.utc)
    return moment.astimezone(ZoneInfo(timezone_name)).date()


def build_card_metadata(metadata: dict) -> dict:
    return {
        key: value
        for key, value in metadata.items()
        if key in PUBLIC_CARD_METADATA_KEYS
    }


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
        code_search_requests_per_minute=settings.code_search_requests_per_minute,
    )

    seed_repos = load_seed_repos()
    skill_seed_repos = load_skill_seed_repos()
    skill_query_seed = today.toordinal()
    skill_code_queries = cycle_queries(build_skill_code_queries(), limit=2, seed=skill_query_seed)
    skill_repo_queries = cycle_queries(build_skill_repo_queries(days_back=30), limit=2, seed=skill_query_seed + 1)
    skill_min_stars = load_skill_min_stars()
    project_min_stars = load_project_min_stars()
    skill_shape_floor = load_skill_shape_floor()
    skill_top_n = load_skill_top_n()
    skill_per_repo_cap = load_skill_per_repo_cap()
    daily_item_count = load_output_daily_item_count_config()
    project_first = bool(daily_item_count["project_first"])
    ossinsight_enabled = load_ossinsight_enabled()
    ossinsight_collector = None
    if ossinsight_enabled:
        ossinsight_collector = OSSInsightCollector(
            client=OSSInsightClient(),
            trending_periods=load_ossinsight_trending_periods(),
            language=load_ossinsight_language(),
            collection_period=load_ossinsight_collection_period(),
            collection_name_keywords=load_ossinsight_collection_name_keywords(),
            max_trending_items=load_ossinsight_max_trending_items(),
            max_collection_ids=load_ossinsight_max_collection_ids(),
        )
    repo_queries = build_repo_queries(now=run_started_at, days_back=7)
    discussion_queries = build_discussion_queries(seed_repos=seed_repos, now=run_started_at, days_back=30)
    issue_pr_queries = build_issue_pr_queries(seed_repos=seed_repos, now=run_started_at, days_back=30)
    skill_search_cost = len(skill_code_queries) + len(skill_repo_queries)
    collector_specs: list[tuple[str, object, int]] = []
    collector_specs.append(("trending", TrendingCollector(), 0))
    if ossinsight_collector:
        collector_specs.append(("ossinsight", ossinsight_collector, 0))
    collector_specs.extend(
        [
            ("repos", RepoCollector(client=client, queries=repo_queries), len(repo_queries)),
            ("discussions", DiscussionCollector(client=client, queries=discussion_queries), len(discussion_queries)),
            ("issues_prs", IssuesPrsCollector(client=client, queries=issue_pr_queries), len(issue_pr_queries)),
            (
                "skills",
                SkillCollector(
                    client=client,
                    code_queries=skill_code_queries,
                    repo_queries=skill_repo_queries,
                    seed_repos=skill_seed_repos,
                    skill_min_stars=skill_min_stars,
                    project_min_stars=project_min_stars,
                    skill_shape_floor=skill_shape_floor,
                    top_n=skill_top_n,
                    per_repo_cap=skill_per_repo_cap,
                ),
                skill_search_cost,
            ),
        ]
    )

    candidates = []
    collector_errors: list[dict[str, str]] = []
    collector_stats: dict[str, dict] = {}
    collector_skips: list[dict[str, str]] = []
    for collector_name, collector, estimated_search_cost in collector_specs:
        remaining_search_budget = client._budget.search_budget - client._budget.search_used
        if estimated_search_cost and remaining_search_budget < estimated_search_cost:
            collector_stats[collector_name] = {
                "count": 0,
                "kinds": {},
                "skipped": "insufficient search budget",
            }
            collector_skips.append(
                {
                    "collector": collector_name,
                    "reason": "insufficient search budget",
                }
            )
            continue
        try:
            collected = collector.collect()
            candidates.extend(collected)
            collector_stats[collector_name] = {
                "count": len(collected),
                "kinds": dict(Counter(item.kind for item in collected)),
            }
        except Exception as exc:  # noqa: BLE001 - keep one collector failure from stopping the rest
            collector_errors.append({"collector": collector_name, "error": str(exc)})
            collector_stats[collector_name] = {"count": 0, "kinds": {}, "error": str(exc)}

    raw_candidate_count = len(candidates)
    unique_candidates = []
    seen_candidate_ids: set[str] = set()
    for candidate in candidates:
        if candidate.candidate_id in seen_candidate_ids:
            continue
        seen_candidate_ids.add(candidate.candidate_id)
        unique_candidates.append(candidate)
    candidates = unique_candidates

    state.record_seen(today, candidates)

    filtered = []
    for candidate in candidates:
        if state.is_in_cooldown(candidate.candidate_id, settings.cooldown_days, today):
            if should_reenter(candidate):
                filtered.append(candidate)
        else:
            filtered.append(candidate)

    ranked_candidates = sorted(filtered, key=score_candidate, reverse=True)
    fallback_models = [settings.fallback_model] if settings.fallback_model else []
    llm = EditorialLLM(
        api_key=settings.qwen_api_key,
        model=settings.default_model,
        fallback_models=fallback_models,
    )
    def _editorial_payload(item):
        raw_signals = item.raw_signals or {}
        hints = {
            key: value
            for key, value in {
                "collection_name": raw_signals.get("collection_name"),
                "matched_file": raw_signals.get("matched_file"),
                "matched_path": raw_signals.get("matched_path"),
                "ossinsight_source": item.source_query if item.source_query.startswith("ossinsight:") else "",
            }.items()
            if value
        }
        return {
            "title": item.title,
            "kind": item.kind,
            "url": item.url,
            "repo": item.repo_full_name,
            "description": item.body_excerpt[:280],
            "topics": item.topics,
            "labels": item.labels,
            "source_query": item.source_query,
            "signals": {
                "stars": item.metrics.stars,
                "forks": item.metrics.forks,
                "comments": item.metrics.comments,
                "reactions": item.metrics.reactions,
                "star_growth_7d": item.metrics.star_growth_7d,
                "previous_star_growth_7d": item.metrics.previous_star_growth_7d,
                "has_new_release": item.metrics.has_new_release,
                "days_since_previous_release": item.metrics.days_since_previous_release,
                "comment_growth_rate": item.metrics.comment_growth_rate,
            },
            "hints": hints,
        }

    editorial = llm.rank_and_summarize(
        [_editorial_payload(item) for item in ranked_candidates[: settings.llm_max_candidates]]
    )

    metadata = {
        "count": len(filtered),
        "editorial": len(editorial),
    }
    if collector_errors:
        metadata["collector_errors"] = len(collector_errors)
        metadata["coverage_note"] = "Reduced coverage due to collector failure(s)."
    if collector_skips:
        metadata["collector_skips"] = len(collector_skips)
        metadata["coverage_note"] = "Reduced coverage due to search budget guard."
    api_usage = client._budget.snapshot()
    metadata["api_usage"] = api_usage
    metadata["collector_stats"] = collector_stats
    display_items = build_display_items(filtered, editorial)
    if settings.report_limit > 0:
        display_items = display_items[: settings.report_limit]
    published_items = select_top_items(
        display_items,
        min_items=int(daily_item_count["min"]),
        max_items=int(daily_item_count["max"]),
        per_repo_cap=skill_per_repo_cap,
        project_first=project_first,
    )
    filtered_kind_counts = Counter(item.kind for item in filtered)
    published_kind_counts = Counter(item["kind"] for item in published_items)
    metadata["item_count"] = len(published_items)
    metadata["filtered_kind_counts"] = dict(filtered_kind_counts)
    metadata["published_kind_counts"] = dict(published_kind_counts)
    card = build_digest_card(
        items=published_items,
        metadata=build_card_metadata(metadata),
        today=today,
        project_first=project_first,
    )
    cards = [card]

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
                "raw_candidate_count": raw_candidate_count,
                "selected_count": len(published_items),
                "filtered_kind_counts": dict(filtered_kind_counts),
                "published_kind_counts": dict(published_kind_counts),
                "collector_stats": collector_stats,
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
