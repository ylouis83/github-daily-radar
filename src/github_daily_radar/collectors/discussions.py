import logging

from github_daily_radar.collectors.base import Collector
from github_daily_radar.models import Candidate
from github_daily_radar.normalize.candidates import candidate_from_issue_search


logger = logging.getLogger(__name__)


class DiscussionCollector(Collector):
    name = "discussions"

    def __init__(self, client, queries: list[str] | None = None) -> None:
        super().__init__(client)
        self.queries = queries or [
            "proposal OR rfc OR idea OR design in:title,body comments:>=3",
        ]

    def collect(self) -> list[Candidate]:
        candidates: list[Candidate] = []
        for query in self.queries:
            try:
                payload = self.client.search_issues(query, sort="comments", order="desc")
            except Exception as exc:  # noqa: BLE001 - keep other queries running when one query is rejected
                logger.warning("DiscussionCollector query failed for %s: %s", query, exc, exc_info=True)
                continue
            for item in payload.get("items", []):
                candidates.append(
                    candidate_from_issue_search(item=item, source_query=query, kind="discussion")
                )
        return candidates
