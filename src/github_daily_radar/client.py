from dataclasses import dataclass
from threading import Lock
from time import monotonic, sleep

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential


def _is_retryable_http_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


@dataclass
class BudgetTracker:
    total_budget: int
    search_budget: int
    graphql_budget: int
    search_used: int = 0
    graphql_used: int = 0

    def consume_search(self) -> None:
        if self.search_used >= self.search_budget:
            raise RuntimeError("search budget exhausted")
        self.search_used += 1

    def consume_graphql(self, cost: int) -> None:
        if self.graphql_used + cost > self.graphql_budget:
            raise RuntimeError("graphql budget exhausted")
        self.graphql_used += cost

    def snapshot(self) -> dict[str, int]:
        return {
            "total_budget": self.total_budget,
            "search_budget": self.search_budget,
            "graphql_budget": self.graphql_budget,
            "search_used": self.search_used,
            "graphql_used": self.graphql_used,
        }


class GitHubClient:
    def __init__(
        self,
        token: str,
        budget: BudgetTracker,
        search_requests_per_minute: int = 25,
        code_search_requests_per_minute: int = 10,
    ) -> None:
        self._budget = budget
        self._search_lock = Lock()
        self._code_search_lock = Lock()
        self._min_search_interval = 60 / search_requests_per_minute
        self._min_code_search_interval = 60 / code_search_requests_per_minute
        self._next_search_at = 0.0
        self._next_code_search_at = 0.0
        self._http = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    def _throttle_search(self) -> None:
        with self._search_lock:
            now = monotonic()
            wait_for = self._next_search_at - now
            if wait_for > 0:
                sleep(wait_for)
            self._next_search_at = monotonic() + self._min_search_interval

    def _throttle_code_search(self) -> None:
        with self._code_search_lock:
            now = monotonic()
            wait_for = self._next_code_search_at - now
            if wait_for > 0:
                sleep(wait_for)
            self._next_code_search_at = monotonic() + self._min_code_search_interval

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), retry=retry_if_exception(_is_retryable_http_error))
    def search_code(
        self,
        query: str,
        per_page: int = 20,
        *,
        sort: str | None = None,
        order: str | None = None,
    ) -> dict:
        self._budget.consume_search()
        self._throttle_code_search()
        params = {"q": query, "per_page": per_page}
        if sort:
            params["sort"] = sort
        if order:
            params["order"] = order
        response = self._http.get("/search/code", params=params)
        response.raise_for_status()
        return response.json()

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), retry=retry_if_exception(_is_retryable_http_error))
    def search_repositories(
        self,
        query: str,
        per_page: int = 20,
        *,
        sort: str | None = None,
        order: str | None = None,
    ) -> dict:
        self._budget.consume_search()
        self._throttle_search()
        params = {"q": query, "per_page": per_page}
        if sort:
            params["sort"] = sort
        if order:
            params["order"] = order
        response = self._http.get("/search/repositories", params=params)
        response.raise_for_status()
        return response.json()

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), retry=retry_if_exception(_is_retryable_http_error))
    def search_issues(
        self,
        query: str,
        per_page: int = 20,
        *,
        sort: str | None = None,
        order: str | None = None,
    ) -> dict:
        self._budget.consume_search()
        self._throttle_search()
        params = {"q": query, "per_page": per_page}
        if sort:
            params["sort"] = sort
        if order:
            params["order"] = order
        response = self._http.get("/search/issues", params=params)
        response.raise_for_status()
        return response.json()

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), retry=retry_if_exception(_is_retryable_http_error))
    def graphql(self, query: str, variables: dict | None = None, cost: int = 1) -> dict:
        self._budget.consume_graphql(cost=cost)
        response = self._http.post("/graphql", json={"query": query, "variables": variables or {}})
        response.raise_for_status()
        return response.json()


class OSSInsightClient:
    def __init__(self, base_url: str = "https://api.ossinsight.io/v1") -> None:
        self._http = httpx.Client(base_url=base_url, timeout=30.0)

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), retry=retry_if_exception(_is_retryable_http_error))
    def _get(self, path: str, params: dict | None = None) -> dict:
        response = self._http.get(path, params=params or {})
        response.raise_for_status()
        return response.json()

    def list_trending_repos(self, *, period: str, language: str | None = None) -> dict:
        params = {"period": period}
        if language:
            params["language"] = language
        return self._get("/trends/repos/", params=params)

    def list_collections(self) -> dict:
        return self._get("/collections")

    def collection_ranking_by_stars(self, collection_id: int | str, *, period: str = "past_28_days") -> dict:
        return self._get(f"/collections/{collection_id}/ranking_by_stars/", params={"period": period})
