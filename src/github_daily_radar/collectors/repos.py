from github_daily_radar.collectors.base import Collector
from github_daily_radar.models import Candidate
from github_daily_radar.normalize.candidates import candidate_from_repo_search


class RepoCollector(Collector):
    name = "repos"

    def __init__(self, client, queries: list[str]) -> None:
        super().__init__(client)
        self.queries = queries

    def collect(self) -> list[Candidate]:
        candidates: list[Candidate] = []
        for query in self.queries:
            payload = self.client.search_repositories(query, sort="updated", order="desc")
            for item in payload.get("items", []):
                candidates.append(candidate_from_repo_search(item=item, source_query=query))
        return candidates
