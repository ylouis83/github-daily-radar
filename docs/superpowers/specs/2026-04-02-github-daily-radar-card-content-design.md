# GitHub Daily Radar Card Content Design

## Goal

Make the daily Feishu card feel less like a flat list and more like an edited Chinese digest.

The current card already has the right information, but the copy is too repetitive:

- many items reuse the same generic sentence pattern
- sections feel visually uniform
- the card does not clearly distinguish projects, skills, and discussions in tone

This supplement focuses on improving the content layer of the card while keeping the same one-card A/B layout.

## Problem Statement

The current card is functionally correct, but it reads too monotonously:

- repeated fallback phrases make the card feel machine-generated
- A and B sections look structurally similar even when their editorial role differs
- items with different kinds of signal are described with the same tone
- the result is harder to scan and less memorable

The goal is not to add more content. The goal is to make the existing content feel more intentionally edited.

## Design Principles

1. Keep the existing single-card A/B structure.
2. Prefer compact Chinese copy over literal English description leakage.
3. Make `project`, `skill`, and `discussion` items feel different in tone.
4. Use small, repeatable editorial templates instead of one universal sentence.
5. Preserve stable, testable behavior.

## Proposed Content Model

Each displayed item should still have:

- `title`
- `badge` or signal chip
- `summary`
- `why_now`

But the copy should be generated with kind-aware templates.

### Project Copy

Project items should use a three-part editorial mental model:

- `是什么`
- `为什么现在`
- `建议先看什么`

Recommended tone:

- confident
- concise
- trend-aware

Example shape:

- `这是近期值得关注的仓库，建议先看 README、最近提交和 release。`
- `OSSInsight 近期热度上升，增量明显。`

### Skill Copy

Skill items should highlight reuse and applicability:

- `能做什么`
- `适合谁`
- `是否值得纳入技能库`

Recommended tone:

- practical
- reusable
- slightly evaluative

Example shape:

- `这是一个可复用的 skill / prompt / rules 资源，适合评估是否纳入技能库。`
- `更像可直接拿来用的能力包，而不是单纯的学习材料。`

### Discussion Copy

Discussion, issue, and PR items should foreground the idea or controversy:

- `争议点`
- `方案方向`
- `还要看什么`

Recommended tone:

- analytical
- editorial
- forward-looking

Example shape:

- `这是一个值得跟进的提案，重点看方案、评论和结论。`
- `当前讨论更像是在定义下一步方向，而不是单纯修 bug。`

## Rendering Structure

The card should keep the one-card A/B layout, but each item should be rendered with more variation:

1. title line
2. signal line
3. summary line or `why now` line

The card renderer should support:

- a stronger signal badge cluster
- different copy templates by `kind`
- no runtime metadata block
- no repeated generic fallback line for every entry

## Fallback Copy Rules

When the LLM does not provide editorial text, the system should not fall back to English excerpts verbatim unless the original content is already Chinese.

Fallback behavior should be:

- Chinese template first
- English excerpt only if explicitly requested in a future phase
- no repeated boilerplate phrase across all kinds

Preferred fallback style:

- project: trend / release / README oriented
- skill: reuse / capability bundle oriented
- discussion: proposal / debate / roadmap oriented

## Signal Emphasis

To avoid flatness, the card should emphasize the most relevant signal for each item:

- project: star velocity or OSSInsight growth
- skill: repo size, reuse potential, or signature-file strength
- discussion: comments, reactions, and maintainer involvement

This signal should appear visually and semantically distinct from the summary sentence.

## Data Model Impact

No new top-level model is required.

However, the display item layer should expose enough information for the renderer to choose templates:

- `kind`
- `summary`
- `why_now`
- `stars`
- `star_delta_1d`
- `star_velocity`
- `source_query`

If needed, the display layer may derive a lightweight `copy_style` internally, but it should not leak into the persisted state model.

## Error Handling

If editorial text is missing or invalid:

- fall back to a Chinese template
- keep the title and link
- keep the signal badge if available
- do not block the whole card

## Testing Strategy

Add tests for:

- project items using project-specific fallback copy
- skill items using skill-specific fallback copy
- discussion items using discussion-specific fallback copy
- no raw English excerpt leakage for fallback text
- card rendering still producing one fused A/B card
- compact item rendering with signal + summary separation

## Success Criteria

The change is successful if the daily card:

- reads less repetitive
- feels more editorial
- distinguishes projects, skills, and discussions by tone
- preserves Chinese-only summary lines in normal operation
- still fits within a single Feishu interactive card

## Out of Scope

This supplement does not:

- change discovery or scoring logic
- change the A/B split rules
- change OSSInsight integration
- change deduplication or state persistence

Those concerns stay in the main design spec and the SkillCollector supplement.
