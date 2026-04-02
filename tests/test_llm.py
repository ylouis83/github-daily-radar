import respx
from httpx import Response

from github_daily_radar.summarize.llm import EditorialLLM

CODING_BASE = "https://coding.dashscope.aliyuncs.com/v1"
COMPAT_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
INTL_BASE = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
CODING_ENDPOINT = f"{CODING_BASE}/chat/completions"
COMPAT_ENDPOINT = f"{COMPAT_BASE}/chat/completions"
INTL_ENDPOINT = f"{INTL_BASE}/chat/completions"


@respx.mock
def test_editorial_llm_posts_chat_request():
    route = respx.post(CODING_ENDPOINT).mock(
        return_value=Response(
            200,
            json={"choices": [{"message": {"content": "[]"}}]},
        )
    )

    client = EditorialLLM(api_key="qwen_test", model="qwen3.5-plus")
    result = client.rank_and_summarize([{"title": "Repo A", "kind": "project", "url": "https://github.com/a/b"}])

    assert route.called is True
    assert result == []


@respx.mock
def test_editorial_llm_parses_json_payload():
    route = respx.post(CODING_ENDPOINT).mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '[{"kind":"project","title":"Repo A","url":"https://github.com/a/b","summary":"中文摘要","why_now":"今天活跃"}]'
                        }
                    }
                ]
            },
        )
    )

    client = EditorialLLM(api_key="qwen_test", model="qwen3.5-plus")
    result = client.rank_and_summarize([{"title": "Repo A", "kind": "project", "url": "https://github.com/a/b"}])

    assert route.called is True
    assert result == [
        {
            "kind": "project",
            "title": "Repo A",
            "url": "https://github.com/a/b",
            "summary": "中文摘要",
            "why_now": "今天活跃",
        }
    ]


@respx.mock
def test_editorial_llm_extracts_json_from_wrapped_text():
    respx.post(CODING_ENDPOINT).mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "Here is the JSON:\n[{\"kind\":\"project\",\"title\":\"Repo A\",\"url\":\"https://github.com/a/b\",\"summary\":\"中文摘要\",\"why_now\":\"热度上升\"}]"
                        }
                    }
                ]
            },
        )
    )

    client = EditorialLLM(api_key="qwen_test", model="qwen3.5-plus")
    result = client.rank_and_summarize([{"title": "Repo A", "kind": "project", "url": "https://github.com/a/b"}])

    assert result == [
        {
            "kind": "project",
            "title": "Repo A",
            "url": "https://github.com/a/b",
            "summary": "中文摘要",
            "why_now": "热度上升",
        }
    ]


@respx.mock
def test_editorial_llm_falls_back_on_error():
    respx.post(CODING_ENDPOINT).mock(
        return_value=Response(500, json={"error": "boom"})
    )

    client = EditorialLLM(api_key="qwen_test", model="qwen3.5-plus")
    result = client.rank_and_summarize([{"title": "Repo A", "kind": "project", "url": "https://github.com/a/b"}])

    assert result == []


@respx.mock
def test_editorial_llm_falls_back_to_intl_region():
    respx.post(COMPAT_ENDPOINT).mock(
        return_value=Response(401, json={"error": "unauthorized"})
    )
    intl_route = respx.post(INTL_ENDPOINT).mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '[{"kind":"project","title":"Repo A","url":"https://github.com/a/b","summary":"中文摘要","why_now":"国际站点可用"}]'
                        }
                    }
                ]
            },
        )
    )

    client = EditorialLLM(
        api_key="qwen_test",
        model="qwen3.5-plus",
        base_urls=[COMPAT_BASE, INTL_BASE],
    )
    result = client.rank_and_summarize([{"title": "Repo A", "kind": "project", "url": "https://github.com/a/b"}])

    assert intl_route.called is True
    assert result == [
        {
            "kind": "project",
            "title": "Repo A",
            "url": "https://github.com/a/b",
            "summary": "中文摘要",
            "why_now": "国际站点可用",
        }
    ]
