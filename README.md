# GitHub Daily Radar

Daily GitHub radar that discovers high-signal repositories, reusable skills, and idea-heavy discussions, then sends a concise Chinese digest to Feishu. Runs fully on GitHub Actions with no frontend.

## Configuration

Required secrets:
- `GITHUB_TOKEN` (Actions default)
- `QWEN_API_KEY`
- `FEISHU_WEBHOOK_URL`

Optional secrets:
- `GITHUB_PAT` for higher REST/GraphQL limits

Optional envs:
- `DRY_RUN` (true/false)
- `TIMEZONE` (default `Asia/Shanghai`)
- `LLM_MODEL` (default `qwen3.5-plus`)
- `LLM_MAX_CANDIDATES` (default `24`)
- `SEARCH_REQUESTS_PER_MINUTE` (default `25`)
- `COOLDOWN_DAYS` (default `14`)

Discovery matrix lives in [`config/radar.yaml`](./config/radar.yaml) and can be edited to shift the daily radar toward different GitHub ecosystems. The older [`seed_repos.yaml`](./seed_repos.yaml) remains as a fallback.

## How It Runs

The workflow `daily-radar.yml` runs on a daily cron and on manual dispatch. It collects candidates, ranks them, asks an editorial LLM for summaries, renders Feishu interactive cards, posts to your webhook, then syncs state artifacts to the `state` branch. Use `dry_run` for testing to skip publishing and state updates.
