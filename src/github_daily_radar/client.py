from dataclasses import dataclass
from threading import Lock
from time import monotonic, sleep

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


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


class GitHubClient:
    def __init__(self, token: str, budget: BudgetTracker, search_requests_per_minute: int = 25) -> None:
        self._budget = budget
        self._search_lock = Lock()
        self._min_search_interval = 60 / search_requests_per_minute
        self._next_search_at = 0.0
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

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), retry=retry_if_exception_type(httpx.HTTPError))
    def search_repositories(self, query: str, per_page: int = 20) -> dict:
        self._budget.consume_search()
        self._throttle_search()
        response = self._http.get("/search/repositories", params={"q": query, "per_page": per_page})
        response.raise_for_status()
        return response.json()

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), retry=retry_if_exception_type(httpx.HTTPError))
    def search_issues(self, query: str, per_page: int = 20) -> dict:
        self._budget.consume_search()
        self._throttle_search()
        response = self._http.get("/search/issues", params={"q": query, "per_page": per_page})
        response.raise_for_status()
        return response.json()

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), retry=retry_if_exception_type(httpx.HTTPError))
    def graphql(self, query: str, variables: dict | None = None, cost: int = 1) -> dict:
        self._budget.consume_graphql(cost=cost)
        response = self._http.post("/graphql", json={"query": query, "variables": variables or {}})
        response.raise_for_status()
        return response.json()
