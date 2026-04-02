from github_daily_radar.collectors.base import Collector
from github_daily_radar.models import Candidate
from github_daily_radar.normalize.candidates import candidate_from_issue_search


class IssuesPrsCollector(Collector):
    name = "issues_prs"

    def __init__(self, client, queries: list[str] | None = None) -> None:
        super().__init__(client)
        self.queries = queries or [
            "proposal OR roadmap OR design in:title,body comments:>=1",
        ]

    def collect(self) -> list[Candidate]:
        candidates: list[Candidate] = []
        for query in self.queries:
            payload = self.client.search_issues(query, sort="updated", order="desc")
            for item in payload.get("items", []):
                kind = "pr" if item.get("pull_request") else "issue"
                candidates.append(
                    candidate_from_issue_search(item=item, source_query=query, kind=kind)
                )
        return candidates
