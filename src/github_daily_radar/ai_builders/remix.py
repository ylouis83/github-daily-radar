"""Remix AI builder feed into Chinese digest text.

Uses the same LLM (Qwen) as the GitHub Daily Radar.
If the LLM call fails, falls back to a structured but un-remixed summary.
"""
from __future__ import annotations

import httpx

SYSTEM_PROMPT = """你是一位专业的 AI 行业内容策展人。你的任务是将原始推文和播客数据整理成一份简洁、有洞察力的中文日报摘要。

规则:
- 每位 Builder 都必须出现在输出中，不要跳过任何人
- 对有深度内容的 Builder，用 2-4 句话总结其关键观点、产品发布或行业洞察
- 对内容较轻的 Builder（纯链接、转推等），用 1 句话简要提及即可
- 使用 Builder 的全名和职位（如 "Box CEO Aaron Levie"），不要用 @handle
- 每条内容必须附上原始链接
- 播客部分：200-400 字的精华摘要，包含至少一句直接引语
- 技术术语保留英文（AI, LLM, GPU, API, agent, token 等）
- 人名、公司名、产品名保留英文
- 语气：像一位懂行的朋友在跟你聊天，专业但不死板
- 不要编造任何内容，只使用提供的数据
- 不要使用破折号（—）"""

USER_PROMPT_TEMPLATE = """请将以下 AI Builder 的最新动态整理成中文日报摘要。

## X/Twitter 动态

{twitter_section}

## 播客

{podcast_section}

## 博客

{blog_section}

请按以下格式输出：
1. 先输出 X/Twitter 部分，每位 Builder 一个段落，所有 Builder 都必须包含
2. 再输出播客部分（如果有）
3. 最后输出博客部分（如果有）

每个内容项必须附上原始 URL。不要跳过任何 Builder。"""


def _format_twitter_for_llm(x_items: list[dict]) -> str:
    """Format X/Twitter feed items for the LLM prompt."""
    if not x_items:
        return "（今日无推文更新）"

    sections = []
    for builder in x_items:
        name = builder.get("name", "Unknown")
        handle = builder.get("handle", "")
        bio = builder.get("bio", "")
        tweets = builder.get("tweets", [])
        if not tweets:
            continue

        lines = [f"### {name} (handle: {handle})"]
        if bio:
            lines.append(f"Bio: {bio}")
        for tweet in tweets:
            text = tweet.get("text", "")
            url = tweet.get("url", "")
            likes = tweet.get("likes", 0)
            lines.append(f"- [{likes} likes] {text}")
            if url:
                lines.append(f"  URL: {url}")
        sections.append("\n".join(lines))

    return "\n\n".join(sections) if sections else "（今日无推文更新）"


def _format_podcast_for_llm(podcast_items: list[dict]) -> str:
    """Format podcast feed items for the LLM prompt."""
    if not podcast_items:
        return "（今日无播客更新）"

    sections = []
    for ep in podcast_items:
        name = ep.get("name", "")
        title = ep.get("title", "")
        url = ep.get("url", "")
        transcript = ep.get("transcript", "")
        # Truncate transcript to avoid blowing up context
        if len(transcript) > 8000:
            transcript = transcript[:8000] + "\n...[transcript truncated]"
        sections.append(
            f"### {name}: {title}\nURL: {url}\n\nTranscript:\n{transcript}"
        )

    return "\n\n".join(sections)


def _format_blog_for_llm(blog_items: list[dict]) -> str:
    """Format blog feed items for the LLM prompt."""
    if not blog_items:
        return "（今日无博客更新）"

    sections = []
    for post in blog_items:
        name = post.get("name", "")
        title = post.get("title", "")
        url = post.get("url", "")
        content = post.get("content", "")
        if len(content) > 4000:
            content = content[:4000] + "\n...[content truncated]"
        sections.append(
            f"### {name}: {title}\nURL: {url}\n\n{content}"
        )

    return "\n\n".join(sections)


def remix_with_llm(
    feed_data: dict,
    *,
    api_key: str,
    model: str = "qwen3.5-plus",
    base_url: str = "https://coding.dashscope.aliyuncs.com/v1",
) -> str:
    """Call the LLM to remix feed data into a Chinese digest.

    Returns the remixed text. Falls back to a raw summary on failure.
    """
    x_items = feed_data.get("x", [])
    podcast_items = feed_data.get("podcasts", [])
    blog_items = feed_data.get("blogs", [])

    # Check if there's any content at all
    if not x_items and not podcast_items and not blog_items:
        return "今日 AI Builder 们没有新动态，明天再来看看！"

    user_prompt = USER_PROMPT_TEMPLATE.format(
        twitter_section=_format_twitter_for_llm(x_items),
        podcast_section=_format_podcast_for_llm(podcast_items),
        blog_section=_format_blog_for_llm(blog_items),
    )

    try:
        with httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=120.0,
        ) as client:
            resp = client.post(
                "/chat/completions",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 4096,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as exc:
        print(f"[ai_builders] LLM remix failed: {exc}, using fallback")
        return _fallback_summary(x_items, podcast_items, blog_items)


def _fallback_summary(
    x_items: list[dict],
    podcast_items: list[dict],
    blog_items: list[dict],
) -> str:
    """Generate a basic structured summary without LLM."""
    lines: list[str] = []

    if x_items:
        for builder in x_items:
            name = builder.get("name", "")
            bio = builder.get("bio", "")
            tweets = builder.get("tweets", [])
            if not tweets:
                continue
            role = bio.split("\n")[0] if bio else ""
            header = f"**{name}**" + (f" ({role})" if role else "")
            lines.append(header)
            for tweet in tweets[:2]:
                text = tweet.get("text", "")[:200]
                url = tweet.get("url", "")
                lines.append(f"  {text}")
                if url:
                    lines.append(f"  {url}")
            lines.append("")

    if podcast_items:
        for ep in podcast_items:
            name = ep.get("name", "")
            title = ep.get("title", "")
            url = ep.get("url", "")
            lines.append(f"🎙️ {name}: {title}")
            if url:
                lines.append(f"  {url}")
            lines.append("")

    if blog_items:
        for post in blog_items:
            name = post.get("name", "")
            title = post.get("title", "")
            url = post.get("url", "")
            lines.append(f"📝 {name}: {title}")
            if url:
                lines.append(f"  {url}")
            lines.append("")

    return "\n".join(lines) if lines else "今日无更新"
