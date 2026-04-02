import json
from typing import Any

import httpx


class EditorialLLM:
    def __init__(self, api_key: str, model: str) -> None:
        self._http = httpx.Client(
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )
        self.model = model

    def _extract_json(self, content: str) -> list[dict]:
        content = content.strip()
        if not content:
            return []
        try:
            parsed = json.loads(content)
            return self._normalize_parsed(parsed)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        start = min([pos for pos in (content.find("["), content.find("{")) if pos >= 0], default=-1)
        if start == -1:
            return []
        end = max(content.rfind("]"), content.rfind("}"))
        if end <= start:
            return []
        snippet = content[start : end + 1]
        try:
            parsed = json.loads(snippet)
            return self._normalize_parsed(parsed)
        except (json.JSONDecodeError, TypeError, ValueError):
            return []

    def _normalize_parsed(self, parsed: Any) -> list[dict]:
        if isinstance(parsed, dict):
            return [parsed]
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        return []

    def rank_and_summarize(self, candidates: list[dict]) -> list[dict]:
        try:
            response = self._http.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "你是 GitHub 日报的主编。只根据给定字段输出中文 JSON。"
                                "返回一个 JSON 数组，每个元素必须包含: "
                                "title, url, kind, summary, why_now。"
                                "可选字段: section, rank。"
                                "summary 与 why_now 各 1 句话，尽量简短。"
                                "不要虚构未提供的事实。"
                            ),
                        },
                        {
                            "role": "user",
                            "content": json.dumps(candidates, ensure_ascii=False),
                        },
                    ],
                },
            )
            response.raise_for_status()
            choices = response.json().get("choices", [])
            if not choices:
                return []
            content = choices[0].get("message", {}).get("content")
            if not content:
                return []
            return self._extract_json(content)
        except (httpx.HTTPError, ValueError, TypeError):
            return []
