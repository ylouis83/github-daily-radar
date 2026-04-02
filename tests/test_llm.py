import respx
from httpx import Response

from github_daily_radar.summarize.llm import EditorialLLM


@respx.mock
def test_editorial_llm_posts_chat_request():
    route = respx.post("https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={"choices": [{"message": {"content": "[]"}}]},
        )
    )

    client = EditorialLLM(api_key="qwen_test", model="codingplan")
    result = client.rank_and_summarize([{"title": "Repo A", "kind": "project", "url": "https://github.com/a/b"}])

    assert route.called is True
    assert result == []


@respx.mock
def test_editorial_llm_parses_json_payload():
    route = respx.post("https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '[{"kind":"project","title":"Repo A","url":"https://github.com/a/b","summary":"中文摘要"}]'
                        }
                    }
                ]
            },
        )
    )

    client = EditorialLLM(api_key="qwen_test", model="codingplan")
    result = client.rank_and_summarize([{"title": "Repo A", "kind": "project", "url": "https://github.com/a/b"}])

    assert route.called is True
    assert result == [
        {
            "kind": "project",
            "title": "Repo A",
            "url": "https://github.com/a/b",
            "summary": "中文摘要",
        }
    ]


@respx.mock
def test_editorial_llm_falls_back_on_error():
    respx.post("https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions").mock(
        return_value=Response(500, json={"error": "boom"})
    )

    client = EditorialLLM(api_key="qwen_test", model="codingplan")
    result = client.rank_and_summarize([{"title": "Repo A", "kind": "project", "url": "https://github.com/a/b"}])

    assert result == []
