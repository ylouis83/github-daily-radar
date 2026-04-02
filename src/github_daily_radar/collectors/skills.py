from datetime import datetime, timezone, timedelta

from github_daily_radar.collectors.base import Collector
from github_daily_radar.models import Candidate
from github_daily_radar.normalize.candidates import (
    candidate_from_code_search,
    candidate_from_graphql_repo,
    candidate_from_repo_search,
)


class SkillCollector(Collector):
    name = "skills"
    seed_recency_days = 30

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

    def _collect_seed_repos(self, seen: set[str]) -> list[Candidate]:
        if not self.seed_repos:
            return []

        aliases: dict[str, str] = {}
        fragments: list[str] = []
        for index, repo_full_name in enumerate(self.seed_repos):
            owner, name = repo_full_name.split("/", 1)
            alias = f"seed_skill_{index}"
            aliases[alias] = repo_full_name
            fragments.append(
                f'''
                {alias}: repository(owner: "{owner}", name: "{name}") {{
                  nameWithOwner
                  url
                  description
                  createdAt
                  updatedAt
                  pushedAt
                  stargazerCount
                  forkCount
                  repositoryTopics(first: 10) {{
                    nodes {{
                      topic {{
                        name
                      }}
                    }}
                  }}
                  releases(last: 1) {{
                    nodes {{
                      name
                      publishedAt
                      url
                    }}
                  }}
                  owner {{
                    login
                  }}
                }}
                '''
            )

        query = "query {\n" + "\n".join(fragments) + "\n}"
        payload = self.client.graphql(query, cost=max(1, len(self.seed_repos)))
        items: list[Candidate] = []
        for alias, repo_full_name in aliases.items():
            node = payload.get("data", {}).get(alias)
            if not node:
                continue
            latest_release = node.get("releases", {}).get("nodes", [])
            release = latest_release[0] if latest_release else None
            if not self._is_recent_skill_repo(node.get("updatedAt"), release.get("publishedAt") if release else None):
                continue
            candidate = candidate_from_graphql_repo(item=node, source_query=f"seed:{repo_full_name}")
            if candidate.repo_full_name in seen:
                continue
            items.append(candidate)
            seen.add(candidate.repo_full_name)
        return items

    def _is_recent_skill_repo(self, updated_at: str | None, release_published_at: str | None) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.seed_recency_days)
        for value in (updated_at, release_published_at):
            if not value:
                continue
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if moment >= cutoff:
                return True
        return False

    def collect(self) -> list[Candidate]:
        candidates: list[Candidate] = []
        seen: set[str] = set()

        for query in self.code_queries:
            payload = self.client.search_code(query)
            for item in payload.get("items", []):
                candidate = candidate_from_code_search(item=item, source_query=query)
                candidate.kind = "skill"
                if candidate.repo_full_name in seen:
                    continue
                seen.add(candidate.repo_full_name)
                candidates.append(candidate)

        for query in self.repo_queries:
            payload = self.client.search_repositories(query, sort="updated", order="desc")
            for item in payload.get("items", []):
                candidate = candidate_from_repo_search(item=item, source_query=query)
                candidate.kind = "skill"
                if candidate.repo_full_name in seen:
                    continue
                seen.add(candidate.repo_full_name)
                candidates.append(candidate)

        candidates.extend(self._collect_seed_repos(seen))
        return self._dedupe(candidates)
