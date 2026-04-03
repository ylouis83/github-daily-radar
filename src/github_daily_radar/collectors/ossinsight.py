import logging

from github_daily_radar.client import OSSInsightClient
from github_daily_radar.collectors.base import Collector
from github_daily_radar.models import Candidate
from github_daily_radar.normalize.candidates import candidate_from_ossinsight_repo


logger = logging.getLogger(__name__)


def _payload_rows(payload: dict) -> list[dict]:
    data = payload.get("data")
    if isinstance(data, dict):
        rows = data.get("rows")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    rows = payload.get("rows")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


class OSSInsightCollector(Collector):
    name = "ossinsight"

    def __init__(
        self,
        client: OSSInsightClient,
        trending_periods: list[str],
        *,
        language: str = "All",
        collection_period: str = "past_28_days",
        collection_name_keywords: list[str] | None = None,
        collection_name_exclude_keywords: list[str] | None = None,
        max_trending_items: int = 20,
        max_collection_ids: int = 3,
    ) -> None:
        super().__init__(client)
        self.trending_periods = [period for period in trending_periods if isinstance(period, str) and period.strip()]
        self.language = language
        self.collection_period = collection_period
        self.collection_name_keywords = [keyword.lower() for keyword in (collection_name_keywords or []) if keyword.strip()]
        self.collection_name_exclude_keywords = [
            keyword.lower() for keyword in (collection_name_exclude_keywords or []) if keyword.strip()
        ]
        self.max_trending_items = max(1, max_trending_items)
        self.max_collection_ids = max(1, max_collection_ids)

    def _matches_focus(self, text: str) -> bool:
        lowered = text.lower()
        if any(keyword in lowered for keyword in self.collection_name_exclude_keywords):
            return False
        if not self.collection_name_keywords:
            return True
        return any(keyword in lowered for keyword in self.collection_name_keywords)

    def _combined_text(self, row: dict, collection_name: str | None = None) -> str:
        parts: list[str] = []
        for key in ("repo_name", "description", "repo_description", "repo_about", "collection_names", "name"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value)
            elif isinstance(value, list):
                parts.extend(str(item) for item in value if isinstance(item, str) and item.strip())
        if collection_name:
            parts.append(collection_name)
        return " ".join(parts)

    def _selected_collections(self) -> list[dict]:
        try:
            payload = self.client.list_collections()
        except Exception as exc:  # noqa: BLE001 - OSSInsight should degrade gracefully
            logger.warning("OSSInsight list_collections failed: %s", exc, exc_info=True)
            return []

        selected: list[dict] = []
        for row in _payload_rows(payload):
            collection_id = row.get("id", row.get("collection_id"))
            collection_name = row.get("name", row.get("collection_name"))
            if collection_id is None or not isinstance(collection_name, str):
                continue
            if self._matches_focus(collection_name):
                selected.append({"id": collection_id, "name": collection_name})
            if len(selected) >= self.max_collection_ids:
                break
        return selected

    def _collect_trending(self, seen: set[str]) -> list[Candidate]:
        items: list[Candidate] = []
        for period in self.trending_periods:
            try:
                payload = self.client.list_trending_repos(period=period, language=self.language)
            except Exception as exc:  # noqa: BLE001 - a single failing period should not stop the run
                logger.warning("OSSInsight trending failed for %s: %s", period, exc, exc_info=True)
                continue
            for row in _payload_rows(payload)[: self.max_trending_items]:
                text = self._combined_text(row)
                if not self._matches_focus(text):
                    continue
                candidate = candidate_from_ossinsight_repo(item=row, source_query=f"ossinsight:trending:{period}")
                if candidate.repo_full_name in seen:
                    continue
                seen.add(candidate.repo_full_name)
                items.append(candidate)
        return items

    def _collect_collections(self, seen: set[str]) -> list[Candidate]:
        items: list[Candidate] = []
        for collection in self._selected_collections():
            try:
                payload = self.client.collection_ranking_by_stars(collection["id"], period=self.collection_period)
            except Exception as exc:  # noqa: BLE001 - collection ranking should fail soft
                logger.warning(
                    "OSSInsight collection ranking failed for %s: %s",
                    collection["name"],
                    exc,
                    exc_info=True,
                )
                continue
            for row in _payload_rows(payload)[: self.max_trending_items]:
                text = self._combined_text(row, collection_name=collection["name"])
                if not self._matches_focus(text):
                    continue
                candidate = candidate_from_ossinsight_repo(
                    item=row,
                    source_query=f"ossinsight:collection:{collection['name']}:{self.collection_period}",
                    collection_name=collection["name"],
                )
                if candidate.repo_full_name in seen:
                    continue
                seen.add(candidate.repo_full_name)
                items.append(candidate)
        return items

    def collect(self) -> list[Candidate]:
        seen: set[str] = set()
        candidates = self._collect_trending(seen)
        candidates.extend(self._collect_collections(seen))
        return candidates
