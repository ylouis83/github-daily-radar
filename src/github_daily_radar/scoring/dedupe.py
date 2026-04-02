from __future__ import annotations

from github_daily_radar.models import Candidate


_THEME_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (("claude-code", "claude code", "claude"), "claude_code"),
    (("oh-my-claudecode",), "claude_code"),
    (("codex",), "codex"),
    (("model context protocol", "mcp"), "mcp"),
    (("browser-use", "browser use", "browser"), "browser_automation"),
    (("skill", "skills"), "skill_assets"),
    (("prompt", "prompts", "rules"), "prompt_assets"),
    (("agentic-workflow", "agent workflow", "workflow"), "agent_workflow"),
    (("pydantic-ai", "autogen", "langgraph", "crewai", "smolagents"), "agent_framework"),
    (("agent", "agents"), "agent_framework"),
    (("rag", "graphrag", "retrieval"), "rag"),
    (("vllm", "llama.cpp", "inference"), "inference"),
    (("dify", "open-webui"), "platform"),
    (("tensorflow", "pytorch", "scikit-learn", "keras"), "ml_framework"),
]


def classify_theme_key(
    *,
    title: str = "",
    repo_full_name: str = "",
    body_excerpt: str = "",
    source_query: str = "",
    topics: list[str] | None = None,
    labels: list[str] | None = None,
    kind: str = "other",
    extra_text: str = "",
) -> str:
    parts = [
        title,
        repo_full_name,
        body_excerpt,
        source_query,
        " ".join(topics or []),
        " ".join(labels or []),
        extra_text,
    ]
    blob = " ".join(part for part in parts if isinstance(part, str) and part.strip()).lower()
    for needles, theme in _THEME_PATTERNS:
        if any(needle in blob for needle in needles):
            return theme
    if kind == "skill":
        return "skill_assets"
    if kind in {"discussion", "issue", "pr"}:
        return "discussion_rfc"
    if kind == "project":
        return "ai_project"
    return "other"


def should_reenter(candidate: Candidate) -> bool:
    metrics = candidate.metrics

    if metrics.previous_star_growth_7d > 0:
        if metrics.star_growth_7d >= metrics.previous_star_growth_7d * 2:
            return True

    if metrics.has_new_release and metrics.days_since_previous_release is not None:
        if metrics.days_since_previous_release >= 7:
            return True

    if metrics.comment_growth_rate >= 0.5:
        return True

    return False
