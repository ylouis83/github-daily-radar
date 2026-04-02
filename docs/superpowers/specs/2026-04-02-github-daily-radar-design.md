# GitHub Daily Radar Design

## Goal

Build a GitHub-native daily radar that discovers high-signal repositories, reusable skills, and high-value discussions, then sends a concise Chinese daily digest to Feishu via webhook. The first phase should run entirely on GitHub Actions, require no frontend, and stay reliable enough for unattended daily use.

## Product Outcome

The system produces one daily report with roughly 10-20 items across three buckets:

- `Projects`: new or newly-heating repositories worth attention
- `Skills`: reusable agent skills, prompt/workflow packs, rulesets, automation playbooks, and similar capability bundles
- `Ideas & Discussions`: Discussions, Issues, and PRs containing strong ideas, design proposals, emerging patterns, or debates worth tracking

The report should optimize for signal density instead of exhaustiveness. It should avoid repeating the same content every day, but allow reappearance when something has materially progressed.

## Non-Goals

Phase 1 explicitly does not include:

- a frontend, dashboard, or search UI
- real-time monitoring
- multi-channel delivery beyond Feishu webhook
- personalized recommendation profiles
- long-form research reports
- crawling non-GitHub sources

## User Experience

The daily Feishu push should feel like a strong editor picked the most interesting GitHub developments for the day. Each entry should include:

- title
- link
- what it is
- why it matters today
- a few supporting signals

The digest should be in Chinese, while preserving original English repository or thread titles when useful for recognition.

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
- use REST search only for broad discovery
- use GraphQL for batched metadata enrichment on shortlisted repositories or threads
- add retry with backoff for transient failures and secondary-limit responses
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

The Feishu digest should use a stable interactive card layout instead of plain rich text. Card format is the default for Phase 1 because it provides higher information density, clearer visual grouping, and easier long-term template maintenance.

The card should use a stable layout:

1. `今日概览`
2. `Top Projects`
3. `Top Skills`
4. `Top Ideas / Discussions`
5. `值得继续跟踪`

Suggested daily counts:

- `Projects`: 4-7
- `Skills`: 3-5
- `Ideas / Discussions`: 3-6

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
- `OPENAI_API_KEY` or the final chosen model provider key
- `GITHUB_TOKEN` from GitHub Actions

Repository configuration:

- discovery topics
- seed repositories or organizations
- maximum items per day
- cooling window length
- per-run API budget and per-collector budget slices
- `llm_max_candidates`
- minimum score thresholds
- bootstrap mode controls
- optional time zone and schedule metadata

Secrets belong in GitHub Secrets. Search scope and ranking preferences should live in repository-managed config.

## Workflow Design

The GitHub Actions workflow should support both:

- scheduled daily execution
- manual dispatch for testing and iteration

The workflow should also use a concurrency group so only one run updates state at a time.

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

## Phase 1 Acceptance Criteria

Phase 1 is successful when all of the following are true:

- a GitHub Actions workflow runs daily without a server
- the system discovers projects, skills, and discussions from GitHub
- it outputs a balanced daily digest of roughly 10-20 items
- it avoids noisy repetition across a 14-day window
- it can resurface an item when there is meaningful new progress
- it sends the digest to Feishu via interactive card webhook delivery
- it stores enough state to behave consistently across days
- it leaves debug artifacts when failures occur
- it stays within a declared API budget for a normal daily run
- it prevents concurrent runs from corrupting state

## Open Decisions Carried into Planning

These are implementation choices, not design blockers:

- exact search queries and API mix between REST and GraphQL
- final LLM provider and prompt strategy
- exact ranking weights for each content type
- whether state uses JSON files only or a small SQLite file in the `state` branch

The plan should keep these choices explicit and pick the simplest viable path for Phase 1.
