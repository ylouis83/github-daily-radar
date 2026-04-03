import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
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
    load_ossinsight_collection_name_excludes,
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


SURGE_MIN_DAILY_STARS = 200
SURGE_MAX_ITEMS = 5


def _extract_daily_delta(candidate) -> int:
    """从候选中提取真实日增量；仅 Trending 和 OSSInsight 源可靠。"""
    raw = candidate.raw_signals or {}
    # TrendingCollector: stars_today 是真实日增
    trending_item = raw.get("trending_item")
    if isinstance(trending_item, dict):
        return int(trending_item.get("stars_today", 0))
    # OSSInsight: past_24_hours → 日增; past_week → 周增除以 7
    if candidate.source_query.startswith("ossinsight:trending:past_24_hours"):
        return candidate.metrics.star_growth_7d
    if candidate.source_query.startswith("ossinsight:trending:past_week"):
        return candidate.metrics.star_growth_7d // 7
    if candidate.source_query.startswith("ossinsight:collection:"):
        return candidate.metrics.star_growth_7d // 7
    return 0


def _build_surge_items(candidates: list, *, min_daily_stars: int = SURGE_MIN_DAILY_STARS, max_items: int = SURGE_MAX_ITEMS) -> list[dict]:
    """从全部候选中提取爆款项目，按日增降序，去重同 repo 取最高。

    同 repo 出现在多个 collector 时：
    - 日增量取最大值
    - 总星数优先取 TrendingCollector（有真实总星数），OSSInsight 的 stars 实为增量
    """
    # 第一遍：收集每个 repo 的最佳 delta 和所有候选
    repo_data: dict[str, dict] = {}
    for candidate in candidates:
        delta = _extract_daily_delta(candidate)
        if delta < min_daily_stars:
            continue
        repo = candidate.repo_full_name
        entry = repo_data.get(repo)
        if entry is None:
            repo_data[repo] = {"delta": delta, "candidates": [candidate]}
        else:
            entry["delta"] = max(entry["delta"], delta)
            entry["candidates"].append(candidate)

    sorted_repos = sorted(repo_data.items(), key=lambda x: -x[1]["delta"])
    surge_items = []
    for repo, data in sorted_repos[:max_items]:
        delta = data["delta"]
        # 优先选 TrendingCollector 候选（总星数准确）
        best = data["candidates"][0]
        stars_is_growth = True
        for candidate in data["candidates"]:
            raw = candidate.raw_signals or {}
            if raw.get("trending_item"):
                best = candidate
                stars_is_growth = False
                break
            if not raw.get("ossinsight_stars_is_growth"):
                best = candidate
                stars_is_growth = False

        total_stars = best.metrics.stars
        surge_items.append({
            "title": best.title,
            "url": best.url,
            "repo_full_name": best.repo_full_name,
            "surge_daily_delta": delta,
            "stars": total_stars,
            "stars_is_growth": stars_is_growth,
            "kind": best.kind,
            "candidate_id": best.candidate_id,
            "source_query": best.source_query,
        })
    return surge_items


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
            collection_name_exclude_keywords=load_ossinsight_collection_name_excludes(),
            max_trending_items=load_ossinsight_max_trending_items(),
            max_collection_ids=load_ossinsight_max_collection_ids(),
        )
    repo_queries = build_repo_queries(now=run_started_at, days_back=7)
    discussion_queries = build_discussion_queries(seed_repos=seed_repos, now=run_started_at, days_back=30)
    issue_pr_queries = build_issue_pr_queries(seed_repos=seed_repos, now=run_started_at, days_back=30)
    # 构建 skill 7 天 cooldown 集：最近 7 天已发布的 skill repos 不再重复出现
    skill_cooldown_ids: set[str] = set()
    history = state.read_history()
    cooldown_cutoff = today - timedelta(days=7)
    for entry in history.get("published", []):
        if entry.get("kind") in ("skill", "project"):
            pub_date_str = entry.get("date", "")
            try:
                pub_date = datetime.fromisoformat(pub_date_str).date()
            except (ValueError, TypeError):
                continue
            if pub_date >= cooldown_cutoff:
                cid = entry.get("candidate_id", "")
                if cid:
                    skill_cooldown_ids.add(cid)
                    # 也加 repo_full_name 兜底（candidate_id 格式可能不同）
                    if ":" in cid:
                        skill_cooldown_ids.add(cid.split(":", 1)[1])
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
                    cooldown_repo_ids=skill_cooldown_ids,
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
    previous_run_summary = state.read_last_run_summary() or {}
    blocked_themes: set[str] = set()
    prev_top_themes = previous_run_summary.get("top_themes")
    if isinstance(prev_top_themes, list):
        blocked_themes = {theme for theme in prev_top_themes if isinstance(theme, str) and theme.strip()}
    else:
        prev_theme_counts = previous_run_summary.get("theme_counts")
        if isinstance(prev_theme_counts, dict):
            top_prev: list[tuple[str, int]] = []
            for theme, count in prev_theme_counts.items():
                if not isinstance(theme, str) or not theme.strip():
                    continue
                try:
                    count_value = int(count)
                except (TypeError, ValueError):
                    continue
                top_prev.append((theme, count_value))
            top_prev.sort(key=lambda item: item[1], reverse=True)
            blocked_themes = {theme for theme, count in top_prev[:3] if count > 0}
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

    # ── 爆款提取（从全部 filtered 候选，不是 display_items）──
    surge_items = _build_surge_items(filtered)
    surge_repos = {item["repo_full_name"] for item in surge_items}

    display_items = build_display_items(filtered, editorial)
    if settings.report_limit > 0:
        display_items = display_items[: settings.report_limit]

    # ── 核心项目 7 天冷却：近 7 天已推送的 project 不再出现 ──
    project_cooldown_ids: set[str] = set()
    for entry in history.get("published", []):
        if entry.get("kind") == "project":
            pub_date_str = entry.get("date", "")
            try:
                pub_date = datetime.fromisoformat(pub_date_str).date()
            except (ValueError, TypeError):
                continue
            if (today - pub_date).days < 7:
                repo = entry.get("title") or ""
                if repo:
                    project_cooldown_ids.add(repo)

    # 从 display_items 中排除：已在爆款区的 repo + 7 天内已推送的 project
    display_items_filtered = []
    for item in display_items:
        repo = item.get("repo_full_name", "")
        # 已在爆款区的不进核心项目
        if item.get("kind") == "project" and repo in surge_repos:
            continue
        # 核心项目 7 天冷却（skill / discussion 不受影响）
        if item.get("kind") == "project" and repo in project_cooldown_ids:
            continue
        display_items_filtered.append(item)

    published_items = select_top_items(
        display_items_filtered,
        min_items=int(daily_item_count["min"]),
        max_items=int(daily_item_count["max"]),
        per_repo_cap=skill_per_repo_cap,
        project_first=project_first,
        blocked_themes=blocked_themes,
    )
    filtered_kind_counts = Counter(item.kind for item in filtered)
    published_kind_counts = Counter(item["kind"] for item in published_items)
    theme_counts = Counter(item.get("theme", "other") for item in published_items if item.get("theme"))
    top_themes = [theme for theme, count in theme_counts.most_common(3) if count > 0]
    metadata["item_count"] = len(published_items)
    metadata["surge_count"] = len(surge_items)
    metadata["filtered_kind_counts"] = dict(filtered_kind_counts)
    metadata["published_kind_counts"] = dict(published_kind_counts)
    metadata["theme_counts"] = dict(theme_counts)
    metadata["top_themes"] = top_themes
    card = build_digest_card(
        items=published_items,
        surge_items=surge_items,
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
                "theme_counts": dict(theme_counts),
                "top_themes": top_themes,
                "collector_stats": collector_stats,
                "collector_errors": collector_errors,
                "api_usage": api_usage,
                "timezone": settings.timezone,
            },
        )
        state.record_published(today, published_items)
        state.record_published(today, surge_items)

    return {"cards": cards, "count": len(filtered), "summary": metadata}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alert-only", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()
    run_pipeline(settings=settings, alert_only=args.alert_only)


if __name__ == "__main__":
    main()
