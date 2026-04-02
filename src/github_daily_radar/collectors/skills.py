import logging

from github_daily_radar.collectors.base import Collector
from github_daily_radar.models import Candidate
from github_daily_radar.normalize.candidates import (
    candidate_from_code_search,
    candidate_from_repo_search,
)


logger = logging.getLogger(__name__)


class SkillCollector(Collector):
    name = "skills"

    def __init__(self, client, code_queries: list[str], repo_queries: list[str], seed_repos: list[str] | None = None) -> None:
        super().__init__(client)
        self.code_queries = code_queries
        self.repo_queries = repo_queries
        self.seed_repos = seed_repos or []

    def _dedupe(self, candidates: list[Candidate]) -> list[Candidate]:
        deduped: list[Candidate] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate.repo_full_name in seen:
                continue
            seen.add(candidate.repo_full_name)
            deduped.append(candidate)
        return deduped

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
                candidate.kind = "skill"
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

        return self._dedupe(candidates)
