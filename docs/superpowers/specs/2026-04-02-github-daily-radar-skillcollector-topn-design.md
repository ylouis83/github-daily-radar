# GitHub Daily Radar SkillCollector TopN Design

## Goal

Refine `SkillCollector` so it keeps useful low-star skills, but stops flooding the daily radar with tiny, low-signal repositories.

The new behavior should:

- apply a minimum quality gate before a repo can enter the skill pool
- rank candidates with a mix of "skill shape" and "project scale"
- take a bounded `top_n` instead of letting every weak hit through
- still allow larger, established repositories to appear when they are clearly relevant to the skills ecosystem

This is a focused supplement to the main GitHub Daily Radar design.

## Problem Statement

The current skill discovery path is too permissive:

- any repo that matches a skill-shaped query can enter the pool
- low-star repos with only a weak signal can still be surfaced
- large repos that are clearly useful can be crowded out by small niche repos

The result is a skill section that is technically relevant, but not editorially strong enough for a daily report that should feel curated.

## Design Principles

1. Prefer signal over raw popularity, but do not ignore popularity entirely.
2. Allow strong skill-shape matches to survive even when star counts are low.
3. Prefer larger, more established repos when they also match the skill intent.
4. Keep the collector deterministic and easy to test.
5. Do not add a separate manual curation step in Phase 1.

## Proposed Behavior

`SkillCollector` should treat each candidate as belonging to one of two practical buckets:

- `skill-shaped`: repos that look like reusable skills, prompts, rules, MCP tools, or agent playbooks
- `project-scale`: larger repos that are clearly part of the same ecosystem and deserve to compete for skill slots

Both buckets are merged into one pool, deduplicated by repository, and sorted into a single `top_n` list.

### Admission Rules

A repository can enter the skill pool if either of the following is true:

- it meets a minimum star floor for skills
- it has a strong skill-shape score from signature files, repo keywords, or ecosystem metadata

The collector should also allow larger repos to enter even if their shape score is weaker, as long as they still look related to the skill ecosystem.

Recommended defaults:

- `skill_min_stars = 3`
- `project_min_stars = 20`
- `skill_shape_floor = 2`
- `top_n = 10`
- `per_repo_cap = 1`

These values are intentionally conservative. They keep the lowest-noise items out, but still admit small, useful skill repos.

## Scoring Model

Each skill candidate should carry two explicit signals:

- `skill_shape_score`: how much the repo looks like a reusable skill package
- `project_scale_score`: how large, active, or established the repo is

Suggested inputs:

- signature file hits such as `SKILL.md`, `CLAUDE.md`, `AGENTS.md`, `.cursorrules`, or `mcp.json`
- repo-name and description matches like `cursor rules`, `claude skills`, `mcp server`, `agent workflow`
- stars, forks, recent updates, releases, and OSSInsight growth

Suggested ranking formula:

- `score = 0.45 * skill_shape_score + 0.35 * project_scale_score + 0.15 * recency_score + 0.05 * source_bonus`

The exact coefficients can be tuned later, but the ordering intent should stay the same:

- skill shape matters most
- scale matters enough to surface larger useful projects
- recency nudges active repos upward
- source bonus is only a tie-breaker

## Selection Strategy

After scoring, the collector should:

1. dedupe by repository full name
2. sort by final score descending
3. enforce `per_repo_cap`
4. keep only the first `top_n` candidates

If there are fewer than `top_n` valid candidates, emit the smaller set rather than padding with weak noise.

## Balance Constraint

To keep the section balanced, the collector should try to preserve both of these groups when available:

- at least a few strong skill-shaped repos
- at least a few larger ecosystem repos

This should be implemented as a soft preference, not a hard partition. The collector should still obey final score ordering.

## Data Model Impact

The normalized `Candidate` model does not need a new top-level type, but the following fields or signals should be present in `rule_scores` or `raw_signals`:

- `skill_shape_score`
- `project_scale_score`
- `skill_min_stars_hit`
- `project_min_stars_hit`
- `skill_bucket`

These fields let tests and the digest layer understand why a repo was admitted.

## Error Handling

The collector should remain fail-soft:

- if code search is rate-limited, repo search can still continue
- if repo search is rate-limited, code search can still continue
- if the candidate pool is too small, the collector should return the valid subset instead of fabricating filler items

Budget exhaustion should still be visible in logs and run metadata.

## Testing Strategy

Add focused tests for:

- low-star skill-shaped repos passing the shape gate
- low-star repos failing when neither star floor nor shape threshold is met
- larger repos passing via the scale path
- `top_n` capping behavior
- deduplication by repository
- stable ordering when scores are tied

The test suite should prove that the collector can still discover useful skills while filtering out obvious noise.

## Success Criteria

The change is successful if a typical daily run produces:

- fewer tiny, unhelpful skill entries
- more skill entries that look reusable or ecosystem-relevant
- at least some large, useful repositories in the skill section when they match the skill ecosystem
- a bounded and stable `SkillCollector` output size

## Out of Scope

This supplement does not:

- change OSSInsight collector behavior
- change project collector ranking
- change Feishu card formatting
- change the main deduplication window

Those are covered by the main design spec.
