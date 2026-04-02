# GitHub Daily Radar Design

## Goal

Build a GitHub-native daily radar that discovers high-signal repositories, reusable skills, and high-value discussions, then sends a concise Chinese daily digest to Feishu via webhook. The first phase should run entirely on GitHub Actions, require no frontend, and stay reliable enough for unattended daily use.

## Product Outcome

The system produces one daily report bundle with two Feishu cards:

- `A 精编版`: roughly 8-12 items, optimized for immediate reading and decision-making
- `B 保留版`: roughly 8-12 additional items, optimized for breadth without becoming noisy

Together they should cover roughly 16-24 items across three buckets:

- `Projects`: new or newly-heating repositories worth attention
- `Skills`: reusable agent skills, prompt/workflow packs, rulesets, automation playbooks, and similar capability bundles
- `Ideas & Discussions`: Discussions, Issues, and PRs containing strong ideas, design proposals, emerging patterns, or debates worth tracking

The report should optimize for signal density instead of exhaustiveness. It should avoid repeating the same content every day, but allow reappearance when something has materially progressed. The A card must be strong enough to stand alone; the B card is a structured backup layer, not a dump of leftovers.

## Non-Goals

Phase 1 explicitly does not include:

- a frontend, dashboard, or search UI
- real-time monitoring
- multi-channel delivery beyond Feishu webhook
- personalized recommendation profiles
- long-form research reports
- crawling non-GitHub sources

## User Experience

The daily Feishu push should feel like a strong editor picked the most interesting GitHub developments for the day. The output should read naturally in Chinese, while preserving original English repository or thread titles when useful for recognition. Each entry should include:

- title
- link
- what it is
- why it matters today
- a few supporting signals

The digest should be in Chinese end-to-end:

- card titles, section headers, labels, and summary text should be Chinese
- original English titles should remain clickable and may be lightly annotated, but should not be translated away
- sentence length should stay compact enough to fit a mobile Feishu card without feeling cramped

## Scope

### In Scope

- scheduled daily execution on GitHub Actions
- broad GitHub discovery across repositories, skills, discussions, issues, and PRs
- rule-based candidate discovery and initial ranking
- LLM-assisted refinement, summarization, and final ranking
- 14-day light deduplication window
- state persistence across runs
- Feishu webhook delivery
- artifact retention for debugging
- two-tier Chinese editorial cards (`A 精编版` and `B 保留版`)

### Out of Scope

- account-specific personalization
- inline subscription management
- cross-source content normalization beyond GitHub
- semantic vector retrieval or full-text search interfaces

## Recommended Architecture

Use a mixed pipeline:

1. discover broadly with deterministic collectors
2. normalize into one candidate model
3. score with explicit heuristics
4. refine and summarize with an LLM
5. apply history-aware deduplication and re-entry rules
6. publish to Feishu
7. persist state for the next run

This balances coverage, maintainability, and editorial quality. Rules keep the system stable and cheap. The LLM is used where judgment matters most: summarization, grouping, and final ranking.

## API Budget and Rate Limits

GitHub API budget is a first-class design constraint for Phase 1.

The design should assume:

- REST search has a separate and relatively tight budget from core REST usage
- GraphQL is preferable for batch enrichment after discovery
- GitHub Actions' default `GITHUB_TOKEN` has a lower GraphQL primary rate limit than a normal user token, so the system should be designed around conservative usage instead of optimistic assumptions

Phase 1 should explicitly budget calls by collector. Recommended approach:

- define a per-run `rate_limit_budget`
- give each collector an explicit slice of that budget
- reserve a shared REST search throttle of about `25 requests per minute` so the system stays below the tighter search bucket with operational headroom
- route all REST search traffic through a single throttled client path; search collectors should not fan out concurrent search requests
- use REST search only for broad discovery
- use GraphQL for batched metadata enrichment on shortlisted repositories or threads
- add retry with backoff for transient failures and secondary-limit responses
- reduce request count with curated query bundles where result quality remains acceptable, instead of expanding one request per topic mechanically
- record API usage metrics in the daily run summary

The implementation plan should include a simple call-budget estimate for a full daily run before coding begins.

## Data Model

The system should normalize all sources into a shared `Candidate` structure. Core fields:

- `candidate_id`: deterministic stable identifier
- `kind`: `project`, `skill`, `discussion`, `issue`, or `pr`
- `source_query`: which collector or search produced it
- `title`
- `url`
- `repo_full_name`
- `author`
- `created_at`
- `updated_at`
- `body_excerpt`
- `topics`
- `labels`
- `metrics`
- `raw_signals`
- `rule_scores`
- `llm_summary`
- `llm_reason`
- `final_score`
- `dedupe_key`

`metrics` and `raw_signals` should retain source-specific observables such as stars, forks, reactions, comments, reviewers, release timestamps, and recency deltas.

## Discovery Sources

### Projects

Project collectors should focus on:

- recently created repositories with fast star growth
- existing repositories with notable recent activity and renewed momentum
- repositories with fresh releases or meaningful update bursts
- topic-based discovery for areas like `agent`, `ai`, `llm`, `workflow`, `automation`, `devtools`, `browser-use`, and related tags

Strong project signals:

- recent star acceleration
- recency of pushes
- strong topics and README positioning
- evidence that it is not merely an old established project idling at a high star count

### Skills

Skills should be interpreted broadly, but Phase 1 should avoid expensive full-repository tree inspection during initial discovery. A candidate can qualify if it looks like a reusable capability package, not only if it has a literal `SKILL.md`.

Primary discovery sources for Phase 1:

- repositories surfaced through topic filters and README keyword hits
- known agent ecosystem repositories and seed repository lists
- agent-focused recipes and prompt packs
- workflow collections for Codex, Claude Code, Cline, Cursor, and similar agent ecosystems
- repositories that package automation playbooks, operator manuals, or prompt-driven capability systems

Expensive structure checks such as looking for `SKILL.md`, `skills/`, `prompts/`, `agents/`, `rules/`, or `workflows/` directories should only run on a narrowed shortlist, not on the full candidate pool.

Strong skill signals:

- reusable structure instead of a loose note dump
- presence of examples, scripts, references, or metadata
- evidence of maintenance or active evolution
- evidence of community reuse, referencing, or discussion

### Ideas & Discussions

This collector should cover:

- GitHub Discussions
- Issues
- PRs

Priority should go to threads that look like proposals, architecture debates, RFC-like discussion, or emergent patterns. Likely heuristics:

- titles or labels containing `proposal`, `rfc`, `idea`, `design`, `roadmap`, `discussion`
- high comment and reaction counts
- maintainer participation
- explicit exploration of future direction, not just bug support

The goal is to catch valuable thinking before or during implementation, not only after a project ships.

## Scoring Strategy

### Rule-Based First Pass

Each candidate should receive four coarse scores:

- `novelty`: how new it is, or how materially new its current development is
- `signal`: how much real attention, engagement, or maintainer involvement it has
- `utility`: how reusable, instructive, or strategically useful it appears
- `taste`: a lightweight editorial prior, mostly determined in the LLM pass rather than by complex rules

Projects, skills, and discussions will use different heuristics to populate these dimensions, but the output scale should be shared so the system can rank across content types. In Phase 1, `taste` should be a minimal heuristic signal at rule time and a stronger judgment in the LLM editorial pass.

### LLM Editorial Pass

After rule-based filtering narrows the candidate set, an LLM should:

- summarize each shortlisted candidate in compact Chinese
- explain why it matters today
- classify it into the digest sections
- help rank by combining novelty, relevance, and editorial value

The LLM should not discover raw candidates. It should refine high-potential items surfaced by deterministic discovery.

## History and Deduplication

Use light deduplication, not permanent suppression.

Default behavior:

- do not resend the same item within a 14-day cooling window

Phase 1 should use explicit re-entry thresholds instead of qualitative judgment alone.

Allow re-entry if one of the following is true:

- a repository's short-term star growth is at least 2x the growth seen at the last publish point
- a new release shipped and the previous release is at least 7 days older
- a discussion, issue, or PR increased comment volume by at least 50% since the last publish point
- an idea thread turned into implementation or was adopted upstream
- a skill package became more concrete, complete, or reusable

The implementation may also support a manual allowlist override for force-resurfacing a candidate during the cooling window.

The state system should store:

- daily run summaries
- recently published candidate identifiers
- last-seen and last-published metrics
- optional snapshots of supporting scores

## State Persistence

Persist runtime state in a dedicated Git branch such as `state`, separate from the code branch. This is preferable to cache-only storage because it is durable, inspectable, and versioned.

Suggested stored artifacts:

- `state/history.jsonl` for pushed items
- `state/daily/<date>.json` for daily run output
- `state/cache/*.json` for API-derived intermediate snapshots when useful

The code branch remains clean and reviewable. The state branch carries operational memory.

## Delivery Format

The Feishu digest should use stable interactive cards instead of plain rich text. Card format is the default for Phase 1 because it provides higher information density, clearer visual grouping, and easier long-term template maintenance.

Render two cards in order:

1. `A 精编版`
2. `B 保留版`

The `A` card should use this stable layout:

1. `今日概览`
2. `必看项目`
3. `必看技能`
4. `必看提案 / 讨论`
5. `值得继续跟踪`

The `B` card should use a shorter companion layout:

1. `更多值得扫一眼`
2. `项目补充`
3. `技能补充`
4. `提案 / 讨论补充`

Suggested daily counts:

- `A 精编版`: 8-12 items total
- `B 保留版`: 8-12 items total
- `Projects`: 4-7 across both cards
- `Skills`: 3-5 across both cards
- `Ideas / Discussions`: 6-10 across both cards

## Editorial Upgrade

This section defines the quality bar for the two-card bundle.

### Selection policy

Use a two-tier editorial split:

- `A` contains the highest-confidence, highest-signal candidates after deduplication and diversity filtering
- `B` contains the next-best candidates that are still worth scanning but do not belong in the first card

The split should not be purely chronological. It should be based on:

- combined deterministic score
- editor judgment from the LLM
- source diversity
- topic diversity
- dedupe pressure from repeated repos or repeated threads

The implementation should cap repeated items from the same repo so that one active repository cannot flood the entire digest.

### Chinese copy contract

The LLM editorial pass should emit Chinese for all generated copy:

- `overview`
- `summary`
- `why_now`
- `follow_up` or `continue_tracking`
- section labels

Keep original titles as clickable anchors. For example, the card may show the English PR or repository title as the link text, then use Chinese explanatory lines underneath it.

The copy should follow these constraints:

- one sentence for `summary`
- one sentence for `why now`
- no unsupported facts
- no speculation about implementation details that are not present in the candidate data
- prefer concrete signals such as stars, comments, maintainer participation, release recency, or proposal strength

### A/B composition rules

`A 精编版` should be the part a reader can finish in one quick pass:

- show only the strongest items
- prioritize surprising, strategic, or unusually actionable content
- favor diversity over piling up near-duplicate items from the same repo
- keep each item to a compact Chinese summary plus a short `why now` line

`B 保留版` should be the safety net:

- keep additional worthwhile items that would otherwise be lost
- use shorter copy than A
- emphasize breadth and completeness rather than deep explanation
- avoid repeating the exact same prose used in A when a shorter restatement is enough

### Fallback behavior

If the editorial pass is thin or fails validation:

- still render Chinese card headers and section labels
- fall back to deterministic ranking
- keep the A/B split and item caps
- use shorter Chinese fallback summaries built from source fields only

## Acceptance Criteria

The output is considered improved only if all of the following are true:

- Feishu cards are clearly Chinese
- `A 精编版` and `B 保留版` are both present in the same run
- A reads like an editorial shortlist instead of a raw feed
- B preserves breadth without overwhelming the reader
- repeated repos or repeated threads no longer dominate the digest
- the report stays grounded in source facts and does not invent unsupported claims

If the message would exceed delivery limits, split into:

- one overview message
- one or two continuation messages

Every successful run should also save the full digest as an artifact for debugging and traceability.

## Monitoring and Alerts

The system should make silent failure unlikely.

Phase 1 should include:

- workflow failure alerts to Feishu
- run metadata in the daily digest, including candidate counts, selected counts, API usage, and elapsed time
- workflow concurrency protection so scheduled and manual runs cannot corrupt shared state
- bootstrap-mode handling for the first run, when there is no prior history yet

Bootstrap behavior should prefer a clean initial send plus immediate state initialization so the second run can behave normally.

## Failure Handling

The pipeline should degrade gracefully.

If GitHub collection succeeds but LLM refinement fails:

- publish a simplified digest using rule-ranked entries and terse fallback summaries

If Feishu delivery fails:

- fail the workflow visibly
- retain rendered digest and intermediate data as artifacts

If one collector fails:

- continue with the others when practical
- note reduced coverage in the overview section

If no daily digest is published for multiple consecutive scheduled runs:

- emit an explicit alert rather than only relying on GitHub Actions failure visibility

## Repository Structure

Recommended initial layout:

```text
github-daily-radar/
  src/github_daily_radar/
    client.py
    config.py
    models.py
    main.py
    collectors/
      base.py
      repos.py
      skills.py
      discussions.py
      issues_prs.py
    normalize/
      candidates.py
    scoring/
      rules.py
      dedupe.py
    summarize/
      llm.py
      digest.py
    state/
      store.py
    publish/
      feishu.py
  tests/
  .github/workflows/
    daily-radar.yml
```

`client.py` should encapsulate GitHub REST and GraphQL access, retry, backoff, and rate-limit tracking. `collectors/base.py` should define a shared collector interface so collectors can report candidate counts and budget usage consistently. `issues_prs.py` is intentionally combined for Phase 1 because those discovery paths are structurally similar and do not justify separate maintenance yet.

This structure keeps concerns clear: discovery, normalization, scoring, summarization, persistence, and delivery.

## Configuration

Phase 1 should keep runtime configuration minimal.

Secrets:

- `FEISHU_WEBHOOK_URL`
- `QWEN_API_KEY` or the final chosen provider key
- `GITHUB_TOKEN` from GitHub Actions
- optional `GITHUB_PAT` override for higher REST and GraphQL limits during scheduled runs

Repository configuration:

- discovery topics
- curated search query bundles for repos, skills, and discussion discovery
- seed repositories or organizations
- maximum items per day
- cooling window length
- per-run API budget and per-collector budget slices
- shared `search_requests_per_minute` throttle
- `llm_max_candidates`
- minimum score thresholds
- bootstrap mode controls
- default model and provider override controls
- optional time zone and schedule metadata

Secrets belong in GitHub Secrets. Search scope and ranking preferences should live in repository-managed config.

Phase 1 should ship with a default model profile instead of leaving provider choice fully open. The default editorial model should target `千问的 codingplan`, while allowing explicit provider and model override through configuration for later experimentation or migration.

## Workflow Design

The GitHub Actions workflow should support both:

- scheduled daily execution
- manual dispatch for testing and iteration

The workflow should also use a concurrency group so only one run updates state at a time.

`workflow_dispatch` should expose a `dry_run` boolean input. In dry-run mode, the workflow should:

- execute collection, scoring, LLM refinement, and digest rendering normally
- skip Feishu publishing
- skip state-branch writes
- save rendered output and intermediate artifacts for inspection
- report clearly in logs and run metadata that the run was non-publishing

High-level workflow:

1. checkout code
2. install dependencies
3. load current state
4. fetch current rate-limit context
5. collect candidates within per-collector budgets
6. normalize and score
7. refine with LLM on a capped shortlist
8. render digest card payloads
9. send to Feishu
10. persist updated state
11. upload artifacts
12. send failure alert if needed

## Testing Strategy

Phase 1 should include:

- unit tests for scoring rules
- unit tests for deduplication logic
- unit tests for state read/write logic
- unit tests for Feishu formatting
- a fixed-input snapshot test for digest rendering
- at least one manual-dispatch workflow path for dry-run validation
- unit tests around bootstrap-mode behavior
- unit tests for re-entry threshold logic

The system is editorially complex, so deterministic tests should target ranking inputs and state transitions more than LLM phrasing.

## Time Zone Semantics

Phase 1 should treat `Asia/Shanghai` as the product time zone for all daily semantics.

This affects:

- what counts as "today" in the digest
- daily state file naming
- recency windows shown to the user
- the recommended scheduled send window

The daily workflow should be scheduled for roughly 09:00-10:00 China Standard Time, which corresponds to about 01:00-02:00 UTC depending on the exact cron expression used.

All GitHub timestamps arrive as UTC and should be converted into the product time zone only for daily grouping, display, and state partitioning. Internal comparison logic may still use UTC as long as day-boundary semantics remain correct for `Asia/Shanghai`.

## Bootstrap Behavior

On the first run, the system has no historical memory, so novelty is not very discriminative. Bootstrap mode should explicitly downweight `novelty` and lean more heavily on `signal` and `utility` for first-run ranking.

## Phase 1 Acceptance Criteria

Phase 1 is successful when all of the following are true:

- a GitHub Actions workflow runs daily without a server
- the system discovers projects, skills, and discussions from GitHub
- it outputs a balanced daily digest as a two-card bundle, with `A 精编版` and `B 保留版`
- the two-card bundle covers roughly 16-24 items total across the day
- it avoids noisy repetition across a 14-day window
- it can resurface an item when there is meaningful new progress
- it sends the digest to Feishu via interactive card webhook delivery
- the digest text is Chinese end-to-end, while preserving useful original English titles
- it stores enough state to behave consistently across days
- it leaves debug artifacts when failures occur
- it stays within a declared API budget for a normal daily run
- it prevents concurrent runs from corrupting state

## Open Decisions Carried into Planning

These are implementation choices, not design blockers:

- exact search queries and API mix between REST and GraphQL
- exact editorial prompt wording and fallback phrasing for the Chinese cards
- exact ranking weights for each content type
- whether state uses JSON files only or a small SQLite file in the `state` branch

The plan should keep these choices explicit and pick the simplest viable path for Phase 1.
