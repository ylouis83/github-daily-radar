from __future__ import annotations

import logging
from math import log1p

from github_daily_radar.collectors.base import Collector
from github_daily_radar.models import Candidate
from github_daily_radar.normalize.candidates import candidate_from_code_search, candidate_from_repo_search


logger = logging.getLogger(__name__)

_SKILL_FILE_HINTS: dict[str, int] = {
    "skill.md": 4,
    ".cursorrules": 3,
    "cursorrules.md": 3,
    "claude.md": 3,
    "agents.md": 3,
    "copilot-instructions.md": 2,
    "mcp.json": 2,
}
_SKILL_TEXT_HINTS = (
    "skill",
    "prompt",
    "workflow",
    "agent",
    "rules",
    "mcp",
    "playbook",
    "recipe",
    "recipes",
    "cookbook",
    "instruction",
    "instructions",
    "cursor",
    "claude",
    "codex",
    "automation",
)
class SkillCollector(Collector):
    name = "skills"

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
        self.code_queries = code_queries
        self.repo_queries = repo_queries
        self.seed_repos = seed_repos or []
        self.skill_min_stars = max(1, skill_min_stars)
        self.project_min_stars = max(self.skill_min_stars, project_min_stars)
        self.skill_shape_floor = max(1, skill_shape_floor)
        self.top_n = max(1, min(20, top_n))
        self.per_repo_cap = max(1, per_repo_cap)

    def _text_blob(self, candidate: Candidate) -> str:
        raw_signals = candidate.raw_signals or {}
        code_item = raw_signals.get("code_search_item") or {}
        repo_item = raw_signals.get("search_item") or {}
        graphql_item = raw_signals.get("graphql_item") or {}
        repo_meta = code_item.get("repository") or {}
        parts = [
            candidate.title,
            candidate.body_excerpt,
            code_item.get("name", ""),
            code_item.get("path", ""),
            repo_item.get("name", ""),
            repo_item.get("path", ""),
            repo_meta.get("description", ""),
            graphql_item.get("description", ""),
        ]
        return " ".join(part for part in parts if isinstance(part, str) and part.strip()).lower()

    def _skill_shape_score(self, candidate: Candidate) -> float:
        score = 0.0
        raw_signals = candidate.raw_signals or {}
        code_item = raw_signals.get("code_search_item") or {}
        matched_file = (code_item.get("name") or raw_signals.get("matched_file") or "").lower()
        matched_path = (code_item.get("path") or raw_signals.get("matched_path") or "").lower()

        for hint, bonus in _SKILL_FILE_HINTS.items():
            if hint in matched_file or hint in matched_path:
                score += bonus

        blob = self._text_blob(candidate)
        for hint in _SKILL_TEXT_HINTS:
            if hint in blob:
                score += 1.0

        if candidate.kind == "skill":
            score += 0.5

        return score

    def _project_scale_score(self, candidate: Candidate) -> float:
        metrics = candidate.metrics
        return (
            log1p(max(metrics.stars, 0)) * 8.0
            + log1p(max(metrics.forks, 0)) * 2.5
            + log1p(max(metrics.star_growth_7d, 0)) * 6.0
            + log1p(max(metrics.reactions + metrics.comments, 0)) * 1.5
        )

    def _admit_candidate(self, *, shape_score: float, candidate: Candidate) -> bool:
        stars = candidate.metrics.stars
        shape_hit = shape_score >= self.skill_shape_floor
        project_hit = stars >= self.project_min_stars
        skill_floor_hit = stars >= self.skill_min_stars and shape_score >= 1.0
        return shape_hit or project_hit or skill_floor_hit

    def _classify_kind(self, *, candidate: Candidate, shape_score: float, scale_score: float) -> str:
        raw_signals = candidate.raw_signals or {}
        if raw_signals.get("code_search_item"):
            return "skill"
        if candidate.metrics.stars >= self.project_min_stars and scale_score >= shape_score:
            return "project"
        if scale_score >= shape_score + 2.0 and candidate.metrics.stars >= self.skill_min_stars:
            return "project"
        return "skill"

    def _rank_score(self, *, candidate: Candidate, shape_score: float, scale_score: float, kind: str) -> float:
        star_bonus = 2.0 if candidate.metrics.stars >= self.skill_min_stars else 0.0
        project_bonus = 5.0 if kind == "project" else 0.0
        code_bonus = 2.0 if (candidate.raw_signals or {}).get("code_search_item") else 0.0
        recency_bonus = log1p(max(candidate.metrics.star_growth_7d, 0)) * 2.0
        return shape_score * 10.0 + scale_score + star_bonus + project_bonus + code_bonus + recency_bonus

    def _dedupe_best_repo(self, candidates: list[Candidate]) -> list[Candidate]:
        best_by_repo: dict[str, Candidate] = {}
        for candidate in candidates:
            existing = best_by_repo.get(candidate.repo_full_name)
            if existing is None or (candidate.final_score or 0) > (existing.final_score or 0):
                best_by_repo[candidate.repo_full_name] = candidate
        return list(best_by_repo.values())

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
        if len(ordered) <= self.top_n:
            return ordered

        selected: list[Candidate] = []

        def pick(candidate: Candidate) -> None:
            if candidate not in selected and len(selected) < self.top_n:
                selected.append(candidate)

        if ordered:
            pick(ordered[0])

        if len(selected) < self.top_n:
            missing_kind = None
            if any(item.kind == "project" for item in ordered) and not any(item.kind == "project" for item in selected):
                missing_kind = "project"
            elif any(item.kind == "skill" for item in ordered) and not any(item.kind == "skill" for item in selected):
                missing_kind = "skill"

            if missing_kind:
                for candidate in ordered:
                    if candidate.kind == missing_kind:
                        pick(candidate)
                        break

        for candidate in ordered:
            if len(selected) >= self.top_n:
                break
            pick(candidate)

        return selected[: self.top_n]

    def collect(self) -> list[Candidate]:
        candidates: list[Candidate] = []
        seen: set[str] = set(self.seed_repos)

        for query in self.code_queries:
            try:
                payload = self.client.search_code(query)
            except Exception as exc:  # noqa: BLE001 - one bad code query must not stop skill discovery
                logger.warning("SkillCollector code query failed for %s: %s", query, exc, exc_info=True)
                continue
            for item in payload.get("items", []):
                candidate = candidate_from_code_search(item=item, source_query=query)
                if candidate.repo_full_name in seen:
                    continue
                seen.add(candidate.repo_full_name)
                candidates.append(candidate)

        for query in self.repo_queries:
            try:
                payload = self.client.search_repositories(query, sort="updated", order="desc")
            except Exception as exc:  # noqa: BLE001 - keep scanning the remaining queries
                logger.warning("SkillCollector repo query failed for %s: %s", query, exc, exc_info=True)
                continue
            for item in payload.get("items", []):
                candidate = candidate_from_repo_search(item=item, source_query=query, kind="skill")
                if candidate.repo_full_name in seen:
                    continue
                seen.add(candidate.repo_full_name)
                candidates.append(candidate)

        qualified: list[Candidate] = []
        for candidate in candidates:
            shape_score = self._skill_shape_score(candidate)
            scale_score = self._project_scale_score(candidate)
            if not self._admit_candidate(shape_score=shape_score, candidate=candidate):
                continue

            kind = self._classify_kind(candidate=candidate, shape_score=shape_score, scale_score=scale_score)
            candidate.kind = kind
            candidate.final_score = self._rank_score(
                candidate=candidate,
                shape_score=shape_score,
                scale_score=scale_score,
                kind=kind,
            )
            candidate.rule_scores = {
                **candidate.rule_scores,
                "skill_shape_score": shape_score,
                "project_scale_score": scale_score,
                "skill_min_stars_hit": float(candidate.metrics.stars >= self.skill_min_stars),
                "project_min_stars_hit": float(candidate.metrics.stars >= self.project_min_stars),
                "skill_bucket": kind,
                "skill_final_score": candidate.final_score,
            }
            qualified.append(candidate)

        deduped = self._dedupe_best_repo(qualified)
        return self._select_top_n(deduped)
