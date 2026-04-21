## Goal

Integrate three "research-engine" capabilities into `github-daily-radar` without turning it into a generic multi-source news product:

1. Entity resolution layer
2. Cross-source cluster merging
3. Builder / Maintainer mode

## Scope

- Keep the existing collector -> score -> editorial -> brief -> Feishu pipeline intact
- Add a lightweight intelligence enrichment layer between collection/filtering and scoring/rendering
- Enrich current GitHub radar behavior; do not add large-scale new crawlers

## Design

### 1. Entity resolution

- Resolve each GitHub candidate to a canonical repo entity and maintainer entity
- Build alias indexes from current candidates
- Resolve external tech items and builder signals against the alias indexes

### 2. Cross-source clustering

- Cluster by canonical repo entity
- Aggregate supporting evidence from:
  - GitHub collectors
  - external tech pulse items
  - builder signals
- Feed cluster evidence back into candidate scoring and card copy

### 3. Builder / Maintainer mode

- Keep existing builder sections (`x`, `podcast`, `blog`)
- Add a `maintainer` section derived from GitHub candidate activity
- Prefer maintainers with multiple active repos or strong multi-source evidence

## Intended user-visible changes

- GitHub items can surface "multi-source resonance" instead of only single-source heat
- External tech items can attach back to GitHub repos more reliably
- Builder section can mention linked repos when detected
- Daily brief gains a maintainer watch subsection

## Files likely touched

- `src/github_daily_radar/intelligence.py`
- `src/github_daily_radar/main.py`
- `src/github_daily_radar/daily_brief.py`
- `src/github_daily_radar/summarize/digest.py`
- `src/github_daily_radar/publish/feishu.py`
- `tests/test_intelligence.py`
- related daily brief / digest / main pipeline tests
