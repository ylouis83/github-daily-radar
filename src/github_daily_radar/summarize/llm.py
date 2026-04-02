import logging
import json
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URLS = [
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    "https://dashscope-us.aliyuncs.com/compatible-mode/v1",
]


class EditorialLLM:
    def __init__(self, api_key: str, model: str, base_urls: list[str] | None = None) -> None:
        self._api_key = api_key
        self._base_urls = base_urls or list(DEFAULT_BASE_URLS)
        self.model = model

    def _post_chat_completions(self, *, base_url: str, candidates: list[dict]) -> list[dict]:
        with httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=60.0,
        ) as http_client:
            response = http_client.post(
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
                                "可选字段: follow_up, section, rank。"
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
                logger.warning("Editorial LLM returned an empty response for model=%s at %s", self.model, base_url)
                return []
            content = choices[0].get("message", {}).get("content")
            if not content:
                logger.warning("Editorial LLM returned no content for model=%s at %s", self.model, base_url)
                return []
            parsed = self._extract_json(content)
            if not parsed:
                logger.warning("Editorial LLM response could not be parsed for model=%s at %s", self.model, base_url)
            return parsed

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
        for index, base_url in enumerate(self._base_urls):
            try:
                return self._post_chat_completions(base_url=base_url, candidates=candidates)
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code in {401, 404} and index < len(self._base_urls) - 1:
                    logger.warning(
                        "Editorial LLM endpoint %s returned %s, trying fallback region for model=%s",
                        base_url,
                        status_code,
                        self.model,
                    )
                    continue
                logger.warning(
                    "Editorial LLM request failed for model=%s at %s: %s",
                    self.model,
                    base_url,
                    exc,
                    exc_info=True,
                )
                return []
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                logger.warning(
                    "Editorial LLM request failed for model=%s at %s: %s",
                    self.model,
                    base_url,
                    exc,
                    exc_info=True,
                )
                return []
        return []
