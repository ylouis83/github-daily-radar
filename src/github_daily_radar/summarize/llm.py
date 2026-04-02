import httpx


class EditorialLLM:
    def __init__(self, api_key: str, model: str) -> None:
        self._http = httpx.Client(
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )
        self.model = model

    def rank_and_summarize(self, candidates: list[dict]) -> list[dict]:
        try:
            response = self._http.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "Return compact Chinese JSON summaries for GitHub daily radar candidates. Keep facts grounded in provided fields only.",
                        },
                        {
                            "role": "user",
                            "content": str(candidates),
                        },
                    ],
                },
            )
            response.raise_for_status()
            return response.json().get("choices", [])
        except httpx.HTTPError:
            return []
