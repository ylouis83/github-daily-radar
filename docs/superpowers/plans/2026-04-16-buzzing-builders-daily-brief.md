# Buzzing + Builders Daily Brief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship one Feishu daily brief that combines GitHub Radar, Buzzing-powered Tech Pulse, and AI Builders Builder Watch in a single card.

**Architecture:** Keep GitHub discovery as the primary pipeline, add a Buzzing collector and Builder signal fetch step, normalize them into a `DailyBrief`, then render one three-track Feishu card. Preserve graceful degradation so any non-GitHub source can fail without blocking delivery.

**Tech Stack:** Python, Pydantic, httpx, pytest, GitHub Actions, Feishu interactive cards

---

### Task 1: Add Failing Tests For New Daily Brief Behaviors

**Files:**
- Create: `tests/test_buzzing.py`
- Create: `tests/test_daily_brief.py`
- Modify: `tests/test_feishu.py`
- Modify: `tests/test_main_pipeline.py`
- Modify: `tests/test_workflow_config.py`

- [ ] **Step 1: Write the failing Buzzing parser tests**

```python
def test_parse_buzzing_feed_filters_ai_and_dev_items():
    feed = {
        "title": "Product Hunt 热门",
        "items": [
            {
                "title": "CC-BEEPER - 一款适用于 Claude Code 的浮动式 macOS 页面切换器",
                "summary": "A floating macOS pager for Claude Code",
                "url": "https://www.producthunt.com/r/VFG5QZ4RMQUDYX",
                "date_published": "2026-04-15T19:05:40.336Z",
                "tags": ["Open Source", "Developer Tools", "Artificial Intelligence", "GitHub"],
                "_score": 162,
                "_num_comments": 22,
            },
            {
                "title": "一个普通消费品",
                "summary": "Not relevant",
                "url": "https://example.com/non-tech",
                "date_published": "2026-04-15T19:05:40.336Z",
                "tags": ["Lifestyle"],
                "_score": 10,
                "_num_comments": 0,
            },
        ],
    }

    items = parse_buzzing_feed(feed, source="producthunt")

    assert [item.title for item in items] == ["CC-BEEPER - 一款适用于 Claude Code 的浮动式 macOS 页面切换器"]
    assert items[0].score == 162
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_buzzing.py -q`
Expected: FAIL because `parse_buzzing_feed` does not exist yet.

- [ ] **Step 3: Write failing brief assembly tests**

```python
def test_assemble_daily_brief_promotes_repo_like_buzzing_item_to_github_track():
    github_items = [{"kind": "project", "repo_full_name": "owner/repo", "title": "owner/repo"}]
    buzzing_items = [
        ExternalTechCandidate(
            source="showhn",
            title="owner/repo",
            url="https://github.com/owner/repo",
            summary="ship fast",
            score=220,
            comments=18,
            tags=["Developer Tools", "GitHub"],
            published_at="2026-04-16T00:00:00Z",
        )
    ]

    brief = assemble_daily_brief(
        github_items=github_items,
        tech_candidates=buzzing_items,
        builder_signals=[],
    )

    assert brief.github_radar[0]["external_heat"]["source"] == "showhn"
    assert brief.tech_pulse == []
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_daily_brief.py -q`
Expected: FAIL because `ExternalTechCandidate` and `assemble_daily_brief` do not exist yet.

- [ ] **Step 5: Extend Feishu and workflow tests for the single three-track card**

```python
def test_build_digest_card_renders_github_tech_and_builder_tracks():
    card = build_digest_card(
        items=[{"kind": "project", "title": "owner/repo", "url": "https://github.com/owner/repo"}],
        tech_items=[{"title": "Claude Code pager", "url": "https://www.producthunt.com/r/1", "source_label": "Product Hunt", "why_now": "开发者工具热度很高"}],
        builder_sections={"x": [{"title": "Swyx", "url": "https://x.com/swyx/status/1", "why_now": "Builder 线程值得看"}]},
        today=date(2026, 4, 16),
    )

    text = collect_card_text(card)
    assert "GitHub Radar" in text
    assert "Tech Pulse" in text
    assert "Builder Watch" in text
```

- [ ] **Step 6: Run focused card/workflow tests to verify they fail**

Run: `pytest tests/test_feishu.py tests/test_workflow_config.py -q`
Expected: FAIL because `tech_items`, `builder_sections`, and workflow changes do not exist yet.

### Task 2: Implement Buzzing And Builder Source Models

**Files:**
- Modify: `src/github_daily_radar/models.py`
- Create: `src/github_daily_radar/collectors/buzzing.py`
- Modify: `src/github_daily_radar/collectors/__init__.py`
- Test: `tests/test_buzzing.py`

- [ ] **Step 1: Add source-native models**

```python
class ExternalTechCandidate(BaseModel):
    source: str
    title: str
    url: str
    summary: str = ""
    score: int = 0
    comments: int = 0
    tags: list[str] = Field(default_factory=list)
    published_at: str


class BuilderSignal(BaseModel):
    source: str
    title: str
    url: str
    creator: str
    summary: str = ""
    score: int = 0
    published_at: str
    section: Literal["x", "podcast", "blog"]
```

- [ ] **Step 2: Implement the Buzzing parser and collector**

```python
DEFAULT_BUZZING_FEEDS = {
    "showhn": "https://showhn.buzzing.cc/feed.json",
    "producthunt": "https://ph.buzzing.cc/feed.json",
    "hn": "https://hn.buzzing.cc/feed.json",
    "devto": "https://dev.buzzing.cc/feed.json",
}

def parse_buzzing_feed(feed: dict, *, source: str) -> list[ExternalTechCandidate]:
    ...


class BuzzingCollector:
    def collect(self) -> list[ExternalTechCandidate]:
        ...
```

- [ ] **Step 3: Run parser tests**

Run: `pytest tests/test_buzzing.py -q`
Expected: PASS

- [ ] **Step 4: Refactor only if tests stay green**

Run: `pytest tests/test_buzzing.py -q`
Expected: PASS

### Task 3: Assemble The Unified Daily Brief

**Files:**
- Modify: `src/github_daily_radar/models.py`
- Create: `src/github_daily_radar/daily_brief.py`
- Modify: `src/github_daily_radar/ai_builders/feed.py`
- Test: `tests/test_daily_brief.py`

- [ ] **Step 1: Add the `DailyBrief` view model**

```python
class DailyBrief(BaseModel):
    github_radar: list[dict] = Field(default_factory=list)
    tech_pulse: list[dict] = Field(default_factory=list)
    builder_watch: dict[str, list[dict]] = Field(default_factory=dict)
    stats: dict = Field(default_factory=dict)
    coverage_notes: list[str] = Field(default_factory=list)
```

- [ ] **Step 2: Add builder signal extraction and brief assembly**

```python
def extract_builder_signals(feed_data: dict) -> list[BuilderSignal]:
    ...


def assemble_daily_brief(*, github_items: list[dict], tech_candidates: list[ExternalTechCandidate], builder_signals: list[BuilderSignal], metadata: dict | None = None) -> DailyBrief:
    ...
```

- [ ] **Step 3: Run brief assembly tests**

Run: `pytest tests/test_daily_brief.py -q`
Expected: PASS

- [ ] **Step 4: Refactor naming and helpers only after green**

Run: `pytest tests/test_daily_brief.py -q`
Expected: PASS

### Task 4: Integrate The Main Pipeline And Render One Card

**Files:**
- Modify: `src/github_daily_radar/main.py`
- Modify: `src/github_daily_radar/publish/feishu.py`
- Modify: `src/github_daily_radar/ai_builders/main.py`
- Modify: `.github/workflows/daily-radar.yml`
- Test: `tests/test_feishu.py`
- Test: `tests/test_main_pipeline.py`
- Test: `tests/test_workflow_config.py`

- [ ] **Step 1: Update `build_digest_card` to support all three tracks**

```python
def build_digest_card(
    *,
    items: list[dict],
    tech_items: list[dict] | None = None,
    builder_sections: dict[str, list[dict]] | None = None,
    surge_items: list[dict] | None = None,
    metadata: dict | None = None,
    today: date | None = None,
    project_first: bool = True,
) -> dict:
    ...
```

- [ ] **Step 2: Wire Buzzing and Builders into `run_pipeline`**

```python
buzzing_items = BuzzingCollector().collect()
builder_feed = fetch_feeds()
builder_signals = extract_builder_signals(builder_feed)
brief = assemble_daily_brief(
    github_items=published_items,
    tech_candidates=buzzing_items,
    builder_signals=builder_signals,
    metadata=metadata,
)
card = build_digest_card(
    items=brief.github_radar,
    tech_items=brief.tech_pulse,
    builder_sections=brief.builder_watch,
    surge_items=surge_items,
    metadata=build_card_metadata(brief.stats),
    today=today,
    project_first=project_first,
)
```

- [ ] **Step 3: Collapse the workflow to the single-card delivery path**

Run: `pytest tests/test_feishu.py tests/test_main_pipeline.py tests/test_workflow_config.py -q`
Expected: PASS

- [ ] **Step 4: Run the broader suite for regression coverage**

Run: `pytest tests/test_buzzing.py tests/test_daily_brief.py tests/test_feishu.py tests/test_main_pipeline.py tests/test_workflow_config.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/github_daily_radar/models.py src/github_daily_radar/collectors/buzzing.py src/github_daily_radar/collectors/__init__.py src/github_daily_radar/daily_brief.py src/github_daily_radar/ai_builders/feed.py src/github_daily_radar/main.py src/github_daily_radar/publish/feishu.py .github/workflows/daily-radar.yml tests/test_buzzing.py tests/test_daily_brief.py tests/test_feishu.py tests/test_main_pipeline.py tests/test_workflow_config.py docs/superpowers/plans/2026-04-16-buzzing-builders-daily-brief.md
git commit -m "feat: ship unified daily brief card"
```
