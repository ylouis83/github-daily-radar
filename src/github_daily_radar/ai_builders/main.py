"""AI Builders daily entrypoint.

AI Builders content is now integrated into the unified Daily Brief card.
This module remains as a compatibility shim for anyone still invoking the
legacy command directly.
"""
from __future__ import annotations

import argparse

from github_daily_radar.config import Settings
from github_daily_radar.main import run_pipeline


def run_ai_builders_pipeline(settings: Settings, *, dry_run: bool = False) -> dict:
    if dry_run:
        settings.dry_run = True
    print("[ai_builders] Integrated into the unified Daily Brief. Delegating to github_daily_radar.main.")
    return run_pipeline(settings=settings)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Builders Daily Digest")
    parser.add_argument("--dry-run", action="store_true", help="Print digest without sending")
    args = parser.parse_args()

    settings = Settings.from_env()
    run_ai_builders_pipeline(settings=settings, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
