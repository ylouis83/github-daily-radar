from typing import Literal

from pydantic import BaseModel, Field


class CandidateMetrics(BaseModel):
    stars: int = 0
    forks: int = 0
    comments: int = 0
    reactions: int = 0
    star_growth_7d: int = 0
    previous_star_growth_7d: int = 0
    has_new_release: bool = False
    days_since_previous_release: int | None = None
    comment_growth_rate: float = 0.0


class Candidate(BaseModel):
    candidate_id: str
    kind: Literal["project", "skill", "discussion", "issue", "pr"]
    source_query: str
    title: str
    url: str
    repo_full_name: str
    author: str
    created_at: str
    updated_at: str
    body_excerpt: str
    topics: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    metrics: CandidateMetrics = Field(default_factory=CandidateMetrics)
    raw_signals: dict = Field(default_factory=dict)
    rule_scores: dict = Field(default_factory=dict)
    dedupe_key: str
    llm_summary: str | None = None
    editorial_rank: int | None = None


class DailyDigest(BaseModel):
    date: str
    items: list[Candidate]
    metadata: dict = Field(default_factory=dict)
