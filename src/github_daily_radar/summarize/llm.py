import logging
import json
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URLS = [
    "https://coding.dashscope.aliyuncs.com/v1",
]
DEFAULT_REQUEST_BATCH_SIZE = 6
KIMI_THINKING_MODEL = "kimi-k2.5"


class EditorialLLM:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_urls: list[str] | None = None,
        fallback_models: list[str] | None = None,
        request_batch_size: int = DEFAULT_REQUEST_BATCH_SIZE,
    ) -> None:
        self._api_key = api_key
        self._base_urls = base_urls or list(DEFAULT_BASE_URLS)
        self.model = model
        self._fallback_models = [
            fallback_model
            for fallback_model in (fallback_models or [])
            if fallback_model and fallback_model != model
        ]
        self._request_batch_size = max(1, request_batch_size)

    def _request_body(self, *, model: str, candidates: list[dict]) -> dict:
        body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 GitHub 日报的中文主编。只根据给定字段输出中文 JSON。"
                        "严格只输出一个 JSON 数组，不要 markdown，不要代码块，不要解释文字。"
                        "每个元素必须包含: title, url, kind, trait, capability, necessity, why_now。"
                        "可选字段: follow_up, section, rank。"
                        "trait、capability、necessity、why_now 各 1 句话，尽量简短。"
                        "trait 要写出该项目最独特的特点，capability 要总结核心能力，necessity 要说明引入或关注的必要性，"
                        "why_now 要说明今天为什么值得看。"
                        "除仓库名、组织名和必要技术名词外，上述文本必须使用简体中文，不要输出英文句子，"
                        "也不要把不同项目写成同一句模板。"
                        "不要虚构未提供的事实。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(candidates, ensure_ascii=False),
                },
            ],
            "temperature": 0.2,
        }
        if model == KIMI_THINKING_MODEL:
            body["enable_thinking"] = False
        return body

    def _post_chat_completions(self, *, base_url: str, model: str, candidates: list[dict]) -> list[dict]:
        with httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=120.0,
        ) as http_client:
            response = http_client.post(
                "/chat/completions",
                json=self._request_body(model=model, candidates=candidates),
            )
            response.raise_for_status()
            choices = response.json().get("choices", [])
            if not choices:
                logger.warning("Editorial LLM returned an empty response for model=%s at %s", model, base_url)
                return []
            content = choices[0].get("message", {}).get("content")
            if not content:
                logger.warning("Editorial LLM returned no content for model=%s at %s", model, base_url)
                return []
            parsed = self._extract_json(content)
            if not parsed:
                logger.warning("Editorial LLM response could not be parsed for model=%s at %s", model, base_url)
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

    def _batch_candidates(self, candidates: list[dict]) -> list[list[dict]]:
        return [
            candidates[start : start + self._request_batch_size]
            for start in range(0, len(candidates), self._request_batch_size)
        ]

    def _rank_batch(self, candidates: list[dict], *, model: str) -> list[dict]:
        for index, base_url in enumerate(self._base_urls):
            try:
                return self._post_chat_completions(base_url=base_url, model=model, candidates=candidates)
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code in {400, 401, 404} and index < len(self._base_urls) - 1:
                    logger.warning(
                        "Editorial LLM endpoint %s returned %s, trying fallback region for model=%s",
                        base_url,
                        status_code,
                        model,
                    )
                    continue
                logger.warning(
                    "Editorial LLM request failed for model=%s at %s: %s",
                    model,
                    base_url,
                    exc,
                    exc_info=True,
                )
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                logger.warning(
                    "Editorial LLM request failed for model=%s at %s: %s",
                    model,
                    base_url,
                    exc,
                    exc_info=True,
                )
        return []

    def rank_and_summarize(self, candidates: list[dict]) -> list[dict]:
        if not candidates:
            return []

        model_candidates = [self.model, *self._fallback_models]
        results: list[dict] = []
        for batch in self._batch_candidates(candidates):
            batch_results: list[dict] = []
            for model in model_candidates:
                batch_results = self._rank_batch(batch, model=model)
                if batch_results:
                    if model != self.model:
                        logger.warning(
                            "Editorial LLM fell back from model=%s to %s for batch size=%s",
                            self.model,
                            model,
                            len(batch),
                        )
                    break
            offset = len(results)
            for local_index, item in enumerate(batch_results, start=1):
                normalized = dict(item)
                raw_rank = normalized.get("rank", normalized.get("editorial_rank"))
                if raw_rank is None:
                    normalized["rank"] = offset + local_index
                else:
                    try:
                        normalized["rank"] = offset + int(raw_rank)
                    except (TypeError, ValueError):
                        normalized["rank"] = offset + local_index
                results.append(normalized)
        return results
