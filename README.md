# GitHub Daily Radar

Daily GitHub radar that discovers high-signal repositories, reusable skills, and idea-heavy discussions, then sends a concise Chinese digest to Feishu. Runs fully on GitHub Actions with no frontend.

## Configuration

Required secrets:
- `GITHUB_TOKEN` (Actions default)
- `QWEN_API_KEY` (Coding Plan 专属 API Key，格式通常为 `sk-sp-xxxxx`)
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

Coding Plan 必须配套使用专属 API Key 和专属 Base URL，不能和百炼按量计费的普通 Key 混用。当前项目使用的 OpenAI 兼容 Base URL 是 `https://coding.dashscope.aliyuncs.com/v1`，推荐模型是 `qwen3.5-plus`。

Discovery matrix lives in [`config/radar.yaml`](./config/radar.yaml) and can be edited to shift the daily radar toward different GitHub ecosystems. The older [`seed_repos.yaml`](./seed_repos.yaml) remains as a fallback.

The radar now also borrows from OSSInsight's public trend and collection APIs to surface hot repositories without spending GitHub search budget.

## How It Runs

The workflow `daily-radar.yml` runs on a daily cron and on manual dispatch. It collects candidates, ranks them, asks an editorial LLM for summaries, renders one fused Feishu interactive card with A/B sections, posts to your webhook, then syncs state artifacts to the `state` branch. Use `dry_run` for testing to skip publishing and state updates.
