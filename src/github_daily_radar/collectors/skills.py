from __future__ import annotations

import logging
from math import log1p

from github_daily_radar.collectors.base import Collector
from github_daily_radar.models import Candidate
from github_daily_radar.normalize.candidates import (
    candidate_from_code_search,
    candidate_from_graphql_repo,
    candidate_from_repo_search,
)


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
_SEED_REPO_ALIAS_PREFIX = "seed_skill_"
_SUPER_GROWTH_COOLDOWN_BYPASS = 1000
_EXCLUDED_SKILL_REPOS = {
    "liyupi/ai-guide",
    "AgnosticUI/agnosticui",
}


def _seed_repo_query(seed_repos: list[str]) -> str:
    repo_blocks: list[str] = []
    for index, full_name in enumerate(seed_repos):
        if "/" not in full_name:
            continue
        owner, name = full_name.split("/", 1)
        repo_blocks.append(
            f'''
  {_SEED_REPO_ALIAS_PREFIX}{index}: repository(owner: "{owner}", name: "{name}") {{
    nameWithOwner
    url
    description
    createdAt
    updatedAt
    pushedAt
    stargazerCount
    forkCount
    owner {{
      login
    }}
    repositoryTopics(first: 20) {{
      nodes {{
        topic {{
          name
        }}
      }}
    }}
    releases(first: 1, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
      nodes {{
        publishedAt
        name
      }}
    }}
  }}'''
        )
    return "query SeedSkillRepos {\n" + "\n".join(repo_blocks) + "\n}"


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
        cooldown_repo_ids: set[str] | None = None,
        previous_stars_by_repo: dict[str, int] | None = None,
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
        self.cooldown_repo_ids = cooldown_repo_ids or set()
        self.previous_stars_by_repo = {
            repo: max(0, int(stars))
            for repo, stars in (previous_stars_by_repo or {}).items()
            if isinstance(repo, str) and repo.strip()
        }

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

    def _is_seed_candidate(self, candidate: Candidate) -> bool:
        return bool((candidate.raw_signals or {}).get("seed_repo"))

    def _is_noise_candidate(self, candidate: Candidate) -> bool:
        if self._is_seed_candidate(candidate):
            return False
        return candidate.repo_full_name in _EXCLUDED_SKILL_REPOS

    def _hotness_score(self, candidate: Candidate) -> float:
        metrics = candidate.metrics
        return (
            log1p(max(metrics.star_growth_7d, 0)) * 24.0
            + log1p(max(metrics.stars, 0)) * 6.0
            + log1p(max(metrics.forks, 0)) * 1.5
            + log1p(max(metrics.reactions + metrics.comments, 0)) * 0.8
        )

    def _admit_candidate(self, *, shape_score: float, candidate: Candidate) -> bool:
        stars = candidate.metrics.stars
        # 绝对底线：无论 shape 多高，10 星以下一律不要
        if stars < 10:
            return False
        shape_hit = shape_score >= self.skill_shape_floor and stars >= self.skill_min_stars
        project_hit = stars >= self.project_min_stars
        skill_floor_hit = stars >= self.skill_min_stars and shape_score >= 1.0
        return shape_hit or project_hit or skill_floor_hit

    def _classify_kind(self, *, candidate: Candidate, shape_score: float, scale_score: float) -> str:
        raw_signals = candidate.raw_signals or {}
        # Code search hit (matched a skill fingerprint file) → always skill
        if raw_signals.get("code_search_item"):
            return "skill"
        # Curated seed repos are part of the skill ecosystem by definition.
        if raw_signals.get("seed_repo"):
            return "skill"
        # Repos with meaningful skill/MCP shape signals stay as skill;
        # shape_score >= floor means file hints or multiple text hints matched
        if shape_score >= self.skill_shape_floor:
            return "skill"
        # Low skill signals + high stars → project (caught by SkillCollector
        # repo-search but doesn't look like a reusable skill/tool)
        if candidate.metrics.stars >= self.project_min_stars:
            return "project"
        return "skill"

    def _rank_score(self, *, candidate: Candidate, shape_score: float, scale_score: float, kind: str) -> float:
        star_bonus = 1.5 if candidate.metrics.stars >= self.skill_min_stars else 0.0
        project_bonus = 1.0 if kind == "project" else 0.0
        code_bonus = 2.0 if (candidate.raw_signals or {}).get("code_search_item") else 0.0
        seed_bonus = 1.5 if (candidate.raw_signals or {}).get("seed_repo") else 0.0
        return scale_score + shape_score * 2.0 + star_bonus + project_bonus + code_bonus + seed_bonus

    def _apply_observed_star_growth(self, candidate: Candidate) -> None:
        if candidate.metrics.star_growth_7d > 0:
            return
        previous_stars = self.previous_stars_by_repo.get(candidate.repo_full_name)
        if previous_stars is None:
            return
        candidate.metrics.star_growth_7d = max(0, candidate.metrics.stars - previous_stars)
        candidate.rule_scores = {
            **candidate.rule_scores,
            "observed_star_growth_7d": float(candidate.metrics.star_growth_7d),
        }

    def _cooldown_applies(self, candidate: Candidate) -> bool:
        if candidate.metrics.star_growth_7d > _SUPER_GROWTH_COOLDOWN_BYPASS:
            return False
        if candidate.candidate_id in self.cooldown_repo_ids:
            return True
        if candidate.repo_full_name in self.cooldown_repo_ids:
            return True
        return False

    def _collect_seed_repo_candidates(self, seen: set[str]) -> list[Candidate]:
        if not self.seed_repos:
            return []
        query = _seed_repo_query(self.seed_repos)
        if query.count("repository(") == 0:
            return []
        try:
            payload = self.client.graphql(query)
        except Exception as exc:  # noqa: BLE001 - seed repo enrichment should not block skill discovery
            logger.warning("SkillCollector seed repo graphql failed: %s", exc, exc_info=True)
            return []

        data = payload.get("data") or {}
        candidates: list[Candidate] = []
        for index, seed_repo in enumerate(self.seed_repos):
            item = data.get(f"{_SEED_REPO_ALIAS_PREFIX}{index}")
            if not isinstance(item, dict):
                continue
            candidate = candidate_from_graphql_repo(item=item, source_query=f"seed_repo:{seed_repo}")
            candidate.raw_signals = {
                **candidate.raw_signals,
                "seed_repo": seed_repo,
            }
            candidate.rule_scores = {
                **candidate.rule_scores,
                "seed_repo_hit": 1.0,
            }
            if candidate.repo_full_name in seen:
                continue
            seen.add(candidate.repo_full_name)
            candidates.append(candidate)
        return candidates

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
        seen: set[str] = set()  # seed_repos 不再永久排除，改用 cooldown

        for query in self.code_queries:
            try:
                payload = self.client.search_code(query)
            except Exception as exc:  # noqa: BLE001 - one bad code query must not stop skill discovery
                logger.warning("SkillCollector code query failed for %s: %s", query, exc, exc_info=True)
                continue
            for item in payload.get("items", []):
                candidate = candidate_from_code_search(item=item, source_query=query)
                if candidate.repo_full_name in self.seed_repos:
                    candidate.raw_signals = {
                        **candidate.raw_signals,
                        "seed_repo": candidate.repo_full_name,
                    }
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
                if candidate.repo_full_name in self.seed_repos:
                    candidate.raw_signals = {
                        **candidate.raw_signals,
                        "seed_repo": candidate.repo_full_name,
                    }
                if candidate.repo_full_name in seen:
                    continue
                seen.add(candidate.repo_full_name)
                candidates.append(candidate)

        candidates.extend(self._collect_seed_repo_candidates(seen))

        qualified: list[Candidate] = []
        for candidate in candidates:
            self._apply_observed_star_growth(candidate)
            if self._is_noise_candidate(candidate):
                continue
            shape_score = self._skill_shape_score(candidate)
            scale_score = self._hotness_score(candidate)
            if not self._admit_candidate(shape_score=shape_score, candidate=candidate):
                continue

            kind = self._classify_kind(candidate=candidate, shape_score=shape_score, scale_score=scale_score)
            candidate.kind = kind
            if self._cooldown_applies(candidate):
                continue
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
