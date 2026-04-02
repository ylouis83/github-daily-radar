import respx
from httpx import Response

from github_daily_radar.client import OSSInsightClient
from github_daily_radar.collectors.ossinsight import OSSInsightCollector


@respx.mock
def test_ossinsight_collector_merges_trending_and_collection_rankings():
    respx.get("https://api.ossinsight.io/v1/trends/repos/").mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "rows": [
                        {
                            "repo_name": "owner/trending-repo",
                            "repo_url": "https://github.com/owner/trending-repo",
                            "description": "AI agent repo",
                            "stars": 120,
                            "forks": 10,
                            "total_score": 180,
                            "collection_names": ["Artificial Intelligence"],
                        }
                    ]
                }
            },
        )
    )
    respx.get("https://api.ossinsight.io/v1/collections").mock(
        return_value=Response(
            200,
            json={"data": {"rows": [{"id": 10010, "name": "Artificial Intelligence"}]}},
        )
    )
    respx.get("https://api.ossinsight.io/v1/collections/10010/ranking_by_stars/").mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "rows": [
                        {
                            "repo_name": "owner/collection-repo",
                            "repo_url": "https://github.com/owner/collection-repo",
                            "description": "LLM repo",
                            "current_period_growth": 88,
                            "total": 1000,
                            "collection_names": ["Artificial Intelligence"],
                        }
                    ]
                }
            },
        )
    )

    collector = OSSInsightCollector(
        client=OSSInsightClient(),
        trending_periods=["past_24_hours"],
        language="All",
        collection_period="past_28_days",
        collection_name_keywords=["artificial intelligence"],
        max_trending_items=10,
        max_collection_ids=1,
    )

    items = collector.collect()

    assert {item.repo_full_name for item in items} == {"owner/trending-repo", "owner/collection-repo"}
    assert all(item.kind == "project" for item in items)
