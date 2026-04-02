# GitHub Daily Radar Single-Card AI Focus Design

## Status

This spec supersedes the earlier A/B card content supplement and the SkillCollector top-N supplement. It becomes the authoritative design for the final daily digest shape.

## Goal

Ship a single Feishu daily card that feels editorially curated, strongly favors core AI technical content, and keeps the daily output focused on reusable skills, MCP/tooling, AI projects, and only a small amount of high-signal discussion.

The daily report should:

- render as one card only
- merge the old A/B views into one fused report
- give `skills / MCP / tools` and `projects` the majority of space
- keep `discussions / proposals` as a supplement
- stay centered on AI, agentic workflows, frameworks, inference, tooling, and related core AI infrastructure

## Product Outcome

The system produces one Chinese digest per day with roughly 10-20 items total. The output should feel like an edited AI radar, not a noisy list dump.

The fused card should show:

- a compact overview
- one primary section for `MCP / Skills`
- one primary section for `Projects`
- one smaller section for `Discussions / Proposals`
- a concise footer with the date and high-level counts

The old A/B distinction is removed entirely. There is no secondary card and no "scan-only" fallback section.

## Non-Goals

Phase 1 does not include:

- any A/B split or two-card output
- a frontend or dashboard
- personalized feeds
- non-GitHub sources
- broad general-tech coverage outside the AI/core-agent/tooling lane
- runtime debugging metadata inside the user-facing card

If the system cannot fit the daily selection into one card cleanly, it should reduce the item count rather than split into another card.

## User Experience

The card should read like a single editor-picked brief:

- Chinese summary lines, not raw English excerpts
- each item should feel distinct and specific
- skill and MCP items should dominate the main body
- project items should still be substantial
- discussion items should be short and clearly secondary

Each item should keep the same editorial shape:

- title line
- signal line
- `特点`
- `核心能力`
- `引入必要性` or `纳入必要性`

## Scope

### In Scope

- single-card Feishu rendering
- unified ranking across all candidates
- dynamic item count from 10 to 20
- skills / MCP / tools weighted as the primary section
- projects weighted as the second major section
- discussions weighted as a smaller support section
- stronger AI relevance gating
- dynamic skill/MCP admission thresholds
- cumulative star / scale weighting for skill-like items
- Chinese fallback copy when LLM output is missing or weak
- cross-section de-duplication by repository or thread
- state persistence and deduplication across runs

### Out of Scope

- multiple cards per day
- A/B presentation variants
- generic tech discovery without strong AI relevance
- separate manual curation queues
- non-Chinese final copy as a normal fallback path

## Recommended Architecture

Use one pipeline with one unified candidate pool:

1. discover candidates from GitHub and OSSInsight
2. normalize them into one model
3. apply an AI/core-tech relevance gate
4. score them with shared editorial logic
5. generate per-item structured Chinese editorial copy
6. select a single bounded set of 10-20 items
7. render one Feishu card with three sections
8. persist state and run summaries

The key shift is that discovery and ranking are still multi-source, but delivery is now strictly single-card and sectioned by editorial importance.

## Content Focus

The radar should stay centered on these lanes:

- agent frameworks and orchestration
- MCP and tool-use ecosystems
- coding assistants and agentic developer workflows
- LLM inference / serving / runtime / deployment
- RAG / retrieval / memory / evaluation / LLMOps
- prompt / rules / skill / playbook ecosystems
- infrastructure that materially supports AI agents or AI application development

Generic ML or legacy AI libraries should not be allowed in just because they are popular. `tensorflow`, `pytorch`, or `scikit-learn` should only appear if the item has a strong current AI systems / agent / tooling angle and clears the relevance gate.

## Discovery and Relevance Gate

Discovery can still use the existing topics, seed repositories, seed organizations, OSSInsight trends, and skill file searches. But the final selection must pass a stricter relevance gate.

### Projects

Projects should qualify when they show both:

- strong AI/core-tech relevance
- enough momentum to deserve a daily slot

Accepted project signals include:

- agent / agentic / workflow / MCP / browser-use / computer-use / inference / llmops / rag / tooling / framework keywords
- recent star growth or fresh release activity
- OSSInsight growth or collection relevance
- evidence that the repo is part of the current AI tooling conversation, not just a generic AI umbrella project

### Skills / MCP / Tools

The skill-like section should be broader than literal `SKILL.md` discovery, but it must stay high-signal.

An item can qualify when it looks like a reusable capability package, such as:

- skill packs
- prompt packs
- rulesets
- MCP tools or servers
- agent workflows
- reusable playbooks or recipes

This section should use both:

- a minimum entry threshold
- a shape score for reusable capability structure

It should also give extra weight to cumulative popularity signals such as stars, forks, recent commits, and ecosystem reuse. Low-star repos can still enter if they are clearly skill-shaped, but 2-star and 3-star noise should no longer dominate the section.

### Discussions / Proposals

Discussion items should be limited to high-signal threads:

- proposals
- RFCs
- design docs
- roadmap discussions
- architecture debates
- implementation-direction decisions

They should only be admitted when they are clearly related to the AI/core-tech lane or a seed repository in that lane.

## Selection Strategy

The final daily output should be dynamically sized between 10 and 20 items.

Recommended distribution:

- `MCP / Skills`: about 40-50% of the total, and usually the largest section
- `Projects`: about 35-45% of the total
- `Discussions`: about 10-20% of the total

The exact number should be determined by quality:

- start with a target of 10 items
- expand toward 20 only when there are enough strong candidates to justify more slots
- never pad with weak items just to hit the top of the range

The `MCP / Skills` section should be the main beneficiary of extra slots when the pool is strong. The user wants skill-heavy coverage, so this section should generally outrank projects when both are similarly relevant.

### Skill / MCP Top-N Rules

The skill-like section should:

- enforce a minimum gate before admission
- use cumulative stars / forks / recency / shape signals
- prefer skills over generic MCP tools when both are similar in quality
- allow stronger MCP/tool repos to win slots when they are materially more important
- keep the output within a dynamic top 10-20 range instead of always returning everything

Recommended defaults for the ranking system:

- `skill_min_stars`: high enough to remove obvious noise
- `project_min_stars`: higher than the skill floor
- `skill_shape_floor`: enough to preserve real skill-shaped assets
- `top_n`: dynamic within 10-20, not fixed
- `per_repo_cap`: 1

The precise numbers can be tuned in implementation, but the behavior must remain:

- fewer tiny skill repos
- more genuinely reusable skill assets
- enough large AI-tooling repos to compete for the section

## Editorial Copy Model

Each selected item should be rendered with a kind-aware Chinese profile instead of a generic repeated sentence.

The editorial profile should include:

- `特点`
- `核心能力`
- `引入必要性`
- `为什么现在`

Kind-specific tone:

- `project`: trend-aware, concrete, focus on what it is and why it matters now
- `skill` / `MCP`: reuse-aware, capability-oriented, focus on what it can do and why it belongs in a toolchain
- `discussion`: analytical, forward-looking, focus on the idea or decision being debated

If the LLM produces weak or invalid output, the fallback should still be structured Chinese copy derived from signals, not a repeated boilerplate line.

## Rendering Rules

The Feishu card should be a single interactive card with these ordered sections:

1. overview
2. `MCP / Skills`
3. `Projects`
4. `Discussions / Proposals`
5. concise footer

Rendering requirements:

- no A/B labels
- no runtime diagnostics block in the card body
- no empty section placeholder text
- no repeated generic fallback sentence across every item
- keep the Chinese profile lines visually separate

The footer may include only user-facing summary counts, such as the date and total item counts. Raw API usage and internal run metadata should stay in artifacts and state, not in the visible card.

## Failure Handling

The pipeline should remain fail-soft:

- if LLM editorial fails, fall back to structured Chinese templates
- if the skill pool is weak, raise the threshold rather than filling it with noise
- if discussions are weak, omit the section entirely
- if a candidate is not clearly AI/core-tech relevant, drop it
- if a run cannot fit into one card cleanly, shrink the selection instead of splitting cards

## State and Deduplication

State persistence remains unchanged in principle:

- keep daily run summaries
- keep published candidate history
- keep last-seen and last-published metrics
- keep light re-entry rules

The dedupe policy should still allow re-entry when something materially changes, but the visible output should not repeat the same repository just because it appeared in a broader search bucket.

## Testing Strategy

Add or update tests for:

- one-card output with no A/B labels
- `MCP / Skills` section being the dominant section
- `Projects` being the second major section
- `Discussions` being present only when high-signal items exist
- dynamic top 10-20 selection behavior
- stronger admission thresholds for skills/MCP
- AI relevance filtering for generic frameworks
- exclusion of generic OSSInsight collection noise
- fallback Chinese copy without raw English leakage
- no runtime diagnostics block in the card body

## Acceptance Criteria

Phase 1 is successful when all of the following are true:

- the daily report is a single Feishu card
- there is no A/B split anywhere in the visible output
- `MCP / Skills` and `Projects` occupy most of the card
- discussions remain a smaller supporting section
- the final report usually lands between 10 and 20 items
- the skill section is noticeably higher quality than before
- generic low-signal AI/framework noise is filtered out
- the digest remains Chinese-first and editorially specific
- the visible card does not expose runtime diagnostics

