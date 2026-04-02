# GitHub Daily Radar SkillCollector + Card Content Optimizations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** tighten SkillCollector so low-signal repos are filtered while useful skills and larger ecosystem projects still surface, and make the Feishu card copy feel more editorial and less repetitive.

**Architecture:** keep discovery, scoring, and rendering separated. SkillCollector will handle admission + TopN ranking, while the digest layer and Feishu renderer will choose kind-aware Chinese copy templates and richer per-item signals. The main pipeline stays unchanged except for consuming the improved outputs.

**Tech Stack:** Python 3.12, pytest, httpx, pydantic, Feishu interactive cards, GitHub API client.

---

### Task 1: Add skill collector gating and TopN ranking

**Files:**
- Modify: `src/github_daily_radar/collectors/skills.py`
- Modify: `src/github_daily_radar/normalize/candidates.py`
- Test: `tests/test_skill_collector.py`

- [ ] **Step 1: Write the failing test**

```python
def test_skill_collector_applies_star_floor_or_shape_gate():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_skill_collector.py -q`
Expected: FAIL because the collector still admits weak low-star repos without shape gating.

- [ ] **Step 3: Write minimal implementation**

```python
def _skill_shape_score(candidate: Candidate) -> int:
    ...

def _project_scale_score(candidate: Candidate) -> int:
    ...

class SkillCollector(Collector):
    def collect(self) -> list[Candidate]:
        ...
        return top_n_candidates
```

- [ ] **Step 4: Run test to verify it passes**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_skill_collector.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/github_daily_radar/collectors/skills.py src/github_daily_radar/normalize/candidates.py tests/test_skill_collector.py
git commit -m "Tighten skill collector ranking"
```

### Task 2: Improve digest fallback copy and item-level editorial variation

**Files:**
- Modify: `src/github_daily_radar/summarize/digest.py`
- Modify: `src/github_daily_radar/publish/feishu.py`
- Test: `tests/test_digest.py`
- Test: `tests/test_feishu.py`

- [ ] **Step 1: Write the failing test**

```python
def test_project_fallback_summary_uses_chinese_template():
    ...
```

```python
def test_skill_fallback_summary_uses_skill_template():
    ...
```

```python
def test_discussion_fallback_summary_uses_discussion_template():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_digest.py tests/test_feishu.py -q`
Expected: FAIL because fallback still leaks generic repetition and item rendering is too flat.

- [ ] **Step 3: Write minimal implementation**

```python
def _fallback_summary(candidate: Candidate) -> str:
    ...

def _render_item(item: dict, index: int) -> str:
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_digest.py tests/test_feishu.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/github_daily_radar/summarize/digest.py src/github_daily_radar/publish/feishu.py tests/test_digest.py tests/test_feishu.py
git commit -m "Improve digest card copy"
```

### Task 3: Full verification

**Files:**
- No code changes expected

- [ ] **Step 1: Run the full test suite**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q`
Expected: PASS.

- [ ] **Step 2: Sanity-check the rendered card locally or via a dry-run workflow**

Run: `gh workflow run daily-radar.yml --repo ylouis83/github-daily-radar --ref codex/github-daily-radar-impl`
Expected: workflow run succeeds and the rendered card contains mixed project/skill/discussion copy without repetitive English fallbacks.

- [ ] **Step 3: Commit if any final adjustments were needed**

```bash
git add -A
git commit -m "Finalize radar content optimizations"
```

