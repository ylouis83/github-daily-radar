"""AI Builders Digest — main entry point.

Usage:
    python -m github_daily_radar.ai_builders.main

Reads FEISHU_WEBHOOK_URL and QWEN_API_KEY from .env (same as GitHub Daily Radar).
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from github_daily_radar.config import Settings
from github_daily_radar.publish.feishu import send_cards

from .feed import fetch_feeds
from .remix import remix_with_llm
from .card import build_ai_builders_card


def product_today(*, timezone_name: str) -> date:
    return datetime.now(timezone.utc).astimezone(ZoneInfo(timezone_name)).date()


def run_ai_builders_pipeline(settings: Settings, *, dry_run: bool = False) -> dict:
    """Run the AI Builders digest pipeline.

    1. Fetch feeds from follow-builders GitHub repo
    2. Remix with LLM into Chinese digest
    3. Build Feishu card
    4. Push to webhook
    """
    today = product_today(timezone_name=settings.timezone)
    print(f"[ai_builders] Starting digest for {today}")

    # Step 1: Fetch feeds
    print("[ai_builders] Fetching feeds from follow-builders...")
    feed_data = fetch_feeds()
    stats = feed_data["stats"]
    print(
        f"[ai_builders] Fetched: {stats['xBuilders']} builders, "
        f"{stats['totalTweets']} tweets, "
        f"{stats['podcastEpisodes']} podcasts, "
        f"{stats['blogPosts']} blogs"
    )

    if feed_data.get("errors"):
        for err in feed_data["errors"]:
            print(f"[ai_builders] Warning: {err}")

    # Step 2: Check for content
    if stats["xBuilders"] == 0 and stats["podcastEpisodes"] == 0 and stats["blogPosts"] == 0:
        print("[ai_builders] No new content today. Skipping.")
        return {"status": "no_content"}

    # Step 3: Remix with LLM
    print(f"[ai_builders] Remixing with LLM ({settings.default_model})...")
    digest_text = remix_with_llm(
        feed_data,
        api_key=settings.qwen_api_key,
        model=settings.default_model,
        fallback_model="doubao-seed-2.0-pro",
        fallback_base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
        fallback_api_key=settings.volc_api_key,
    )
    print(f"[ai_builders] Digest generated: {len(digest_text)} chars")

    # Step 4: Build card
    card = build_ai_builders_card(
        digest_text=digest_text,
        stats=stats,
        feed_data=feed_data,
        today=today,
    )

    # Step 5: Publish
    if dry_run or settings.dry_run:
        print("[ai_builders] DRY RUN — card not sent")
        print("=" * 60)
        print(digest_text)
        print("=" * 60)
    else:
        print(f"[ai_builders] Sending card to webhook...")
        send_cards(webhook_url=settings.feishu_webhook_url, cards=[card])
        print("[ai_builders] Card sent successfully!")

    return {
        "status": "ok",
        "date": today.isoformat(),
        "stats": stats,
        "digest_length": len(digest_text),
        "card": card,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Builders Daily Digest")
    parser.add_argument("--dry-run", action="store_true", help="Print digest without sending")
    args = parser.parse_args()

    settings = Settings.from_env()
    if args.dry_run:
        settings.dry_run = True

    run_ai_builders_pipeline(settings, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
