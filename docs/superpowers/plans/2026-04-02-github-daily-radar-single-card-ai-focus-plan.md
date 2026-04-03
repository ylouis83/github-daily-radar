# GitHub Daily Radar 单卡 AI 重点版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 GitHub Daily Radar 收敛成一张项目先行的中文日报卡，Projects 放在前面，MCP / Skills 作为第二主轴，Discussions 只做补充，同时把主题冷却加进去，避免连续几天看到同一类内容。

**Architecture:** 统一候选池先从 GitHub / OSSInsight / skill 搜索里拿候选，再在 `main.py` 做单卡编排和主题冷却；`collectors/skills.py` 负责技能 / MCP 的高门槛 TopN；`summarize/digest.py` 负责中文画像和单卡分区顺序；`publish/feishu.py` 只负责单卡渲染并去掉运行时诊断信息；`state/store.py` 负责保存历史主题和发布摘要。这样每层只处理一件事，便于测试和回归。

**Tech Stack:** Python 3.12, pytest, pydantic, httpx, Feishu interactive cards, GitHub REST/GraphQL, OSSInsight public API.

---

### Task 1: 把每日选择改成项目先行的单卡编排

**Files:**
- Modify: `src/github_daily_radar/main.py`
- Modify: `src/github_daily_radar/summarize/digest.py`
- Modify: `config/radar.yaml`
- Test: `tests/test_main_pipeline.py`
- Test: `tests/test_digest.py`

- [ ] **Step 1: 写会失败的测试**

```python
def test_run_pipeline_renders_one_card_with_projects_first(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("QWEN_API_KEY", "qwen_test")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")

    captured = {}

    def fake_build_digest_card(*, items, metadata=None, today=None):
        captured["items"] = items
        captured["metadata"] = metadata or {}
        return {"msg_type": "interactive", "card": {"header": {"title": {"content": "test"}}}}

    monkeypatch.setattr(main_module, "build_digest_card", fake_build_digest_card)
    result = run_pipeline(settings=Settings.from_env())

    assert len(result["cards"]) == 1
    assert len(captured["items"]) >= 10
    assert captured["items"][0]["kind"] == "project"
```

```python
def test_build_digest_card_renders_projects_before_skills():
    card = build_digest_card(
        items=[
            {"kind": "project", "title": "p", "url": "https://github.com/p", "summary": "项目", "stars": 100, "star_delta_1d": 0, "star_velocity": ""},
            {"kind": "skill", "title": "s", "url": "https://github.com/s", "summary": "技能", "stars": 100, "star_delta_1d": 0, "star_velocity": ""},
        ],
        metadata={"count": 2, "published_kind_counts": {"project": 1, "skill": 1}},
        today=date(2026, 4, 2),
    )
    texts = [el["content"] for el in card["card"]["elements"] if el["tag"] == "markdown"]
    joined = "\n".join(texts)
    assert joined.index("🚀 核心 AI 项目") < joined.index("🧩 MCP & Skills Top 10")
```

- [ ] **Step 2: 跑测试确认它先失败**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_main_pipeline.py tests/test_feishu.py tests/test_digest.py -q`
Expected: FAIL，因为现在还没有把“项目先行 + 动态总量”统一收紧。

- [ ] **Step 3: 写最小实现**

```python
def choose_daily_limit(items: list[dict], *, min_items: int = 10, max_items: int = 20) -> int:
    strong = sum(1 for item in items if float(item.get("score", 0.0)) >= 6.0)
    if strong >= 18:
        return 20
    if strong >= 14:
        return 18
    if strong >= 10:
        return 15
    return max(min_items, strong)


def select_top_items(
    items: list[dict],
    *,
    min_items: int = 10,
    max_items: int = 20,
    per_repo_cap: int = 1,
) -> list[dict]:
    ordered = sorted(items, key=_sort_key)
    target = choose_daily_limit(ordered, min_items=min_items, max_items=max_items)
    return _take_diverse_items(ordered, limit=target, per_repo_cap=per_repo_cap)
```

```python
public_metadata = {
    "count": len(filtered),
    "selected_count": len(published_items),
    "published_kind_counts": dict(published_kind_counts),
}
card = build_digest_card(items=published_items, metadata=public_metadata, today=today)
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_main_pipeline.py tests/test_feishu.py tests/test_digest.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/github_daily_radar/main.py src/github_daily_radar/summarize/digest.py config/radar.yaml tests/test_main_pipeline.py tests/test_digest.py
git commit -m "feat: make radar single-card project-first"
```

### Task 2: 收紧 AI / 核心技术相关性门槛，过滤泛化 OSSInsight 噪音

**Files:**
- Modify: `src/github_daily_radar/discovery.py`
- Modify: `src/github_daily_radar/collectors/ossinsight.py`
- Modify: `config/radar.yaml`
- Test: `tests/test_discovery.py`
- Test: `tests/test_ossinsight_collector.py`

- [ ] **Step 1: 写会失败的测试**

```python
@respx.mock
def test_ossinsight_collector_skips_generic_ai_collection():
    respx.get("https://api.ossinsight.io/v1/trends/repos/").mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "rows": [
                        {
                            "repo_name": "tensorflow/tensorflow",
                            "repo_url": "https://github.com/tensorflow/tensorflow",
                            "description": "A machine learning framework",
                            "stars": 10,
                            "forks": 1,
                            "total_score": 20,
                            "collection_names": ["Artificial Intelligence"],
                        }
                    ]
                }
            },
        )
    )
    respx.get("https://api.ossinsight.io/v1/collections").mock(
        return_value=Response(
            200,
            json={"data": {"rows": [{"id": 10010, "name": "Artificial Intelligence"}]}},
        )
    )
    respx.get("https://api.ossinsight.io/v1/collections/10010/ranking_by_stars/").mock(
        return_value=Response(200, json={"data": {"rows": []}})
    )

    collector = OSSInsightCollector(
        client=OSSInsightClient(),
        trending_periods=["past_24_hours"],
        language="All",
        collection_period="past_28_days",
        collection_name_keywords=["agent", "mcp", "llm", "rag", "prompt", "browser-use", "computer-use", "inference"],
        collection_name_exclude_keywords=["artificial intelligence", "machine learning", "deep learning"],
        max_trending_items=10,
        max_collection_ids=1,
    )
    items = collector.collect()
    assert items == []
```

```python
def test_load_ossinsight_collection_name_excludes():
    excludes = load_ossinsight_collection_name_excludes()
    assert "artificial intelligence" in excludes
    assert "machine learning" in excludes
```

- [ ] **Step 2: 跑测试确认它先失败**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_discovery.py tests/test_ossinsight_collector.py -q`
Expected: FAIL，因为现在还没有“排除泛化集合名”的配置和过滤。

- [ ] **Step 3: 写最小实现**

```python
DEFAULT_OSSINSIGHT_COLLECTION_NAME_KEYWORDS = [
    "agent",
    "mcp",
    "llm",
    "rag",
    "prompt",
    "browser-use",
    "computer-use",
    "inference",
]
DEFAULT_OSSINSIGHT_COLLECTION_NAME_EXCLUDES = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
]


def load_ossinsight_collection_name_excludes(path: Path | None = None) -> list[str]:
    raw = load_ossinsight_config(path)
    excludes = raw.get("collection_name_exclude_keywords") or DEFAULT_OSSINSIGHT_COLLECTION_NAME_EXCLUDES
    return [keyword for keyword in excludes if isinstance(keyword, str) and keyword.strip()]
```

```python
def _matches_focus(self, text: str) -> bool:
    lowered = text.lower()
    if any(keyword in lowered for keyword in self.collection_name_excludes):
        return False
    return any(keyword in lowered for keyword in self.collection_name_keywords)
```

```yaml
ossinsight:
  enabled: true
  language: All
  trending_periods:
    - past_24_hours
    - past_week
  collection_period: past_28_days
  collection_name_keywords:
    - agent
    - mcp
    - llm
    - rag
    - prompt
    - browser-use
    - computer-use
    - inference
  collection_name_exclude_keywords:
    - artificial intelligence
    - machine learning
    - deep learning
  max_trending_items: 20
  max_collection_ids: 3
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_discovery.py tests/test_ossinsight_collector.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/github_daily_radar/discovery.py src/github_daily_radar/collectors/ossinsight.py config/radar.yaml tests/test_discovery.py tests/test_ossinsight_collector.py
git commit -m "feat: narrow ossinsight to core ai themes"
```

### Task 3: 把 Skill / MCP 分区抬高门槛并放宽到 20 的上限

**Files:**
- Modify: `src/github_daily_radar/collectors/skills.py`
- Modify: `config/radar.yaml`
- Test: `tests/test_skill_collector.py`
- Test: `tests/test_discovery.py`

- [ ] **Step 1: 写会失败的测试**

```python
def test_skill_collector_rejects_low_star_generic_repo():
    collector = SkillCollector(
        client=FakeClient(
            code_results=[{"repository": {"full_name": "owner/noisy"}, "name": "notes.txt", "path": "notes.txt"}],
            repo_results=[{"full_name": "owner/noisy", "description": "misc repo", "stargazers_count": 2, "forks_count": 0}],
        ),
        code_queries=["filename:notes.txt"],
        repo_queries=["misc in:name,description"],
        seed_repos=[],
        skill_min_stars=80,
        project_min_stars=120,
        skill_shape_floor=3,
        top_n=20,
        per_repo_cap=1,
    )
    assert collector.collect() == []
```

```python
def test_skill_collector_keeps_shape_strong_low_star_repo():
    collector = SkillCollector(
        client=FakeClient(
            code_results=[{"repository": {"full_name": "owner/skill"}, "name": "SKILL.md", "path": "skills/SKILL.md"}],
            repo_results=[],
        ),
        code_queries=["filename:SKILL.md path:skills"],
        repo_queries=[],
        seed_repos=[],
        skill_min_stars=80,
        project_min_stars=120,
        skill_shape_floor=3,
        top_n=20,
        per_repo_cap=1,
    )
    items = collector.collect()
    assert len(items) == 1
    assert items[0].kind == "skill"
```

- [ ] **Step 2: 跑测试确认它先失败**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_skill_collector.py tests/test_discovery.py -q`
Expected: FAIL，因为当前阈值和 TopN 还没有按新的更严格策略收紧。

- [ ] **Step 3: 写最小实现**

```python
class SkillCollector(Collector):
    def __init__(
        self,
        client,
        code_queries: list[str],
        repo_queries: list[str],
        seed_repos: list[str] | None = None,
        *,
        skill_min_stars: int = 80,
        project_min_stars: int = 120,
        skill_shape_floor: int = 3,
        top_n: int = 20,
        per_repo_cap: int = 1,
    ) -> None:
        super().__init__(client)
        self.skill_min_stars = max(1, skill_min_stars)
        self.project_min_stars = max(self.skill_min_stars + 10, project_min_stars)
        self.skill_shape_floor = max(1, skill_shape_floor)
        self.top_n = max(10, min(20, top_n))
        self.per_repo_cap = max(1, per_repo_cap)

    def _select_top_n(self, candidates: list[Candidate]) -> list[Candidate]:
        ordered = sorted(
            candidates,
            key=lambda candidate: (
                -(candidate.final_score or 0.0),
                0 if candidate.kind == "project" else 1,
                -candidate.metrics.stars,
                candidate.repo_full_name,
            ),
        )
        return ordered[: self.top_n]
```

```yaml
skills:
  ranking:
    skill_min_stars: 80
    project_min_stars: 120
    skill_shape_floor: 3
    top_n: 20
    per_repo_cap: 1
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_skill_collector.py tests/test_discovery.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/github_daily_radar/collectors/skills.py config/radar.yaml tests/test_skill_collector.py tests/test_discovery.py
git commit -m "feat: tighten skill collector topn"
```

### Task 4: 清理中文画像、页脚和单卡渲染，去掉运行时信息

**Files:**
- Modify: `src/github_daily_radar/summarize/digest.py`
- Modify: `src/github_daily_radar/publish/feishu.py`
- Modify: `src/github_daily_radar/main.py`
- Test: `tests/test_digest.py`
- Test: `tests/test_feishu.py`

- [ ] **Step 1: 写会失败的测试**

```python
def test_build_display_items_uses_kind_specific_chinese_fallbacks():
    items = build_display_items(
        [
            Candidate(
                candidate_id="repo:owner/project",
                kind="project",
                source_query="topic:agent",
                title="owner/project",
                url="https://github.com/owner/project",
                repo_full_name="owner/project",
                author="owner",
                created_at="2026-04-01T00:00:00Z",
                updated_at="2026-04-02T00:00:00Z",
                body_excerpt="english project text that should not leak",
                topics=["agent"],
                labels=[],
                metrics=CandidateMetrics(stars=12, forks=3),
                raw_signals={},
                rule_scores={},
                dedupe_key="owner/project",
            ),
            Candidate(
                candidate_id="skill:owner/skill",
                kind="skill",
                source_query="filename:SKILL.md path:skills",
                title="owner/skill",
                url="https://github.com/owner/skill",
                repo_full_name="owner/skill",
                author="owner",
                created_at="2026-04-01T00:00:00Z",
                updated_at="2026-04-02T00:00:00Z",
                body_excerpt="english skill text that should not leak",
                topics=["agent"],
                labels=[],
                metrics=CandidateMetrics(stars=8, forks=2),
                raw_signals={},
                rule_scores={},
                dedupe_key="owner/skill",
            ),
            Candidate(
                candidate_id="discussion:owner/thread",
                kind="discussion",
                source_query="proposal",
                title="owner/thread",
                url="https://github.com/owner/project/discussions/1",
                repo_full_name="owner/project",
                author="owner",
                created_at="2026-04-01T00:00:00Z",
                updated_at="2026-04-02T00:00:00Z",
                body_excerpt="english discussion text that should not leak",
                topics=[],
                labels=[],
                metrics=CandidateMetrics(comments=15),
                raw_signals={},
                rule_scores={},
                dedupe_key="owner/thread",
            ),
        ],
        editorial=[],
    )
    assert "english" not in items[0]["summary"].lower()
    assert "特点：" in items[0]["summary"]
    assert "纳入必要性：" in items[1]["summary"]
    assert "跟进必要性：" in items[2]["summary"]
```

```python
def test_build_digest_card_footer_omits_runtime_metrics():
    card = build_digest_card(
        items=[{"kind": "project", "title": "p", "url": "https://github.com/p", "summary": "项目", "stars": 100, "star_delta_1d": 0, "star_velocity": ""}],
        metadata={"count": 1, "published_kind_counts": {"project": 1}},
        today=date(2026, 4, 2),
    )
    texts = [el["content"] for el in card["card"]["elements"] if el["tag"] == "markdown"]
    joined = "\n".join(texts)
    assert "Search" not in joined
    assert "GraphQL" not in joined
    assert "LLM 精编" not in joined
```

```python
def test_build_digest_card_does_not_accept_secondary_items_anymore():
    try:
        build_digest_card(items=[], secondary_items=[], today=date(2026, 4, 2))
    except TypeError:
        return
    assert False, "build_digest_card should reject secondary_items"
```

- [ ] **Step 2: 跑测试确认它先失败**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_digest.py tests/test_feishu.py -q`
Expected: FAIL，因为当前页脚还在显示运行指标，而且 `secondary_items` 仍然存在。

- [ ] **Step 3: 写最小实现**

```python
def build_digest_card(
    *,
    items: list[dict],
    metadata: dict | None = None,
    today: date | None = None,
) -> dict:
    metadata = metadata or {}
    date_str = today.isoformat() if today else ""


def _render_footer(today: date | None = None, metadata: dict | None = None) -> str:
    parts = []
    if today:
        parts.append(f"📅 {today.isoformat()}")
    if metadata:
        count = metadata.get("count")
        published_kind_counts = metadata.get("published_kind_counts") or {}
        if count is not None:
            parts.append(f"精选 {count} 条")
        if published_kind_counts:
            kind_parts = []
            if published_kind_counts.get("project"):
                kind_parts.append(f"{published_kind_counts['project']} 项目")
            if published_kind_counts.get("skill"):
                kind_parts.append(f"{published_kind_counts['skill']} 技能")
            if published_kind_counts.get("discussion"):
                kind_parts.append(f"{published_kind_counts['discussion']} 讨论")
            if kind_parts:
                parts.append(" · ".join(kind_parts))
    return " | ".join(parts)
```

```python
public_metadata = {
    "count": len(filtered),
    "published_kind_counts": dict(published_kind_counts),
}
card = build_digest_card(items=published_items, metadata=public_metadata, today=today)
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_digest.py tests/test_feishu.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/github_daily_radar/summarize/digest.py src/github_daily_radar/publish/feishu.py src/github_daily_radar/main.py tests/test_digest.py tests/test_feishu.py
git commit -m "feat: clean up digest card rendering"
```

### Task 5: 加主题冷却，避免连续几天重复同一类主题

**Files:**
- Modify: `src/github_daily_radar/state/store.py`
- Modify: `src/github_daily_radar/scoring/dedupe.py`
- Modify: `src/github_daily_radar/main.py`
- Modify: `src/github_daily_radar/summarize/digest.py`
- Test: `tests/test_state_store.py`
- Test: `tests/test_main_pipeline.py`

- [ ] **Step 1: 写会失败的测试**

```python
def test_theme_cooldown_blocks_repeat_theme_without_new_signal(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    store = StateStore(base_dir=Path("artifacts/state"))
    store.record_run_summary(date(2026, 4, 1), {"dominant_theme": "claude_code", "theme_counts": {"claude_code": 8}})
    item = {"candidate_id": "project:owner/name", "theme_key": "claude_code", "why_now": "普通热度"}
    assert should_suppress_theme(item, store.read_last_run_summary()) is True
```

```python
def test_theme_cooldown_allows_repeat_on_major_new_release(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    store = StateStore(base_dir=Path("artifacts/state"))
    store.record_run_summary(date(2026, 4, 1), {"dominant_theme": "mcp_tools", "theme_counts": {"mcp_tools": 6}})
    item = {"candidate_id": "project:owner/name", "theme_key": "mcp_tools", "why_now": "有新 release", "star_delta_1d": 500}
    assert should_suppress_theme(item, store.read_last_run_summary()) is False
```

- [ ] **Step 2: 跑测试确认它先失败**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_state_store.py tests/test_main_pipeline.py -q`
Expected: FAIL，因为现在还没有把“主题冷却”写入状态与选择流程。

- [ ] **Step 3: 写最小实现**

```python
def theme_key_for_item(item: dict) -> str:
    return item.get("theme_key") or item.get("kind", "other")


def should_suppress_theme(item: dict, last_run_summary: dict | None) -> bool:
    if not last_run_summary:
        return False
    dominant_theme = last_run_summary.get("dominant_theme")
    if dominant_theme != theme_key_for_item(item):
        return False
    return "新 release" not in (item.get("why_now") or "") and float(item.get("star_delta_1d", 0)) < 300
```

```python
theme_counts = Counter(theme_key_for_item(item) for item in display_items)
dominant_theme = theme_counts.most_common(1)[0][0] if theme_counts else ""
state.record_run_summary(
    today,
    {
        "candidate_count": len(candidates),
        "selected_count": len(published_items),
        "theme_counts": dict(theme_counts),
        "dominant_theme": dominant_theme,
        "filtered_kind_counts": dict(filtered_kind_counts),
        "published_kind_counts": dict(published_kind_counts),
        "collector_stats": collector_stats,
        "collector_errors": collector_errors,
        "api_usage": api_usage,
        "timezone": settings.timezone,
    },
)
```

```python
def read_last_run_summary(self) -> dict | None:
    history = self.read_history()
    summaries = history.get("run_summaries", [])
    return summaries[-1] if summaries else None
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_state_store.py tests/test_main_pipeline.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/github_daily_radar/state/store.py src/github_daily_radar/scoring/dedupe.py src/github_daily_radar/main.py src/github_daily_radar/summarize/digest.py tests/test_state_store.py tests/test_main_pipeline.py
git commit -m "feat: add theme cooldown to radar"
```

### Task 6: 端到端回归和正式前检查

**Files:**
- No code changes expected

- [ ] **Step 1: 跑完整测试套件**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q`
Expected: PASS。

- [ ] **Step 2: 跑一次 GitHub Actions 手动验证**

Run: `gh workflow run daily-radar.yml --repo ylouis83/github-daily-radar --ref codex/github-daily-radar-impl`
Expected: workflow 成功，产物里只剩一张卡，且卡片没有 A/B 标签、没有运行指标块、Projects 在前。

- [ ] **Step 3: 检查产物**

Run: `gh run watch --repo ylouis83/github-daily-radar $(gh run list --repo ylouis83/github-daily-radar --workflow daily-radar.yml --limit 1 --json databaseId -q '.[0].databaseId')`
Expected: 卡片里 `Projects` 分区先出现，`MCP / Skills` 排在后面，讨论只占补充位；连续两天同类主题不会霸屏。
