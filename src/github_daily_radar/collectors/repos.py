import logging

from github_daily_radar.collectors.base import Collector
from github_daily_radar.models import Candidate
from github_daily_radar.normalize.candidates import candidate_from_repo_search


logger = logging.getLogger(__name__)


class RepoCollector(Collector):
    name = "repos"

    def __init__(self, client, queries: list[str]) -> None:
        super().__init__(client)
        self.queries = queries

    def collect(self) -> list[Candidate]:
        candidates: list[Candidate] = []
        for query in self.queries:
            try:
                payload = self.client.search_repositories(query, sort="updated", order="desc")
            except Exception as exc:  # noqa: BLE001 - keep one bad query from dropping the whole collector
                logger.warning("RepoCollector query failed for %s: %s", query, exc, exc_info=True)
                continue
            for item in payload.get("items", []):
                candidates.append(candidate_from_repo_search(item=item, source_query=query))
        return candidates
