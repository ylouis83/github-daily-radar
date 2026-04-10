"""Remix AI builder feed into Chinese digest text.

Uses the same LLM (Qwen) as the GitHub Daily Radar.
If the LLM call fails, falls back to doubao-seed-2.0-pro, then to a
structured but un-remixed summary.
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
        for tweet in tweets[:3]:  # Cap at 3 tweets per builder to reduce prompt size
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
        if len(transcript) > 4000:
            transcript = transcript[:4000] + "\n...[transcript truncated]"
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


def _call_llm(
    *,
    messages: list[dict],
    api_key: str,
    model: str,
    base_url: str,
    timeout: float = 240.0,
) -> str | None:
    """Make a single LLM API call. Returns content string or None on failure."""
    try:
        with httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        ) as client:
            resp = client.post(
                "/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 4096,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as exc:
        print(
            f"[ai_builders] LLM call failed ({model} @ {base_url}): "
            f"{type(exc).__name__}: {exc}"
        )
        if hasattr(exc, "response"):
            try:
                print(f"[ai_builders]   HTTP {exc.response.status_code}: {exc.response.text[:500]}")
            except Exception:
                pass
        return None


def remix_with_llm(
    feed_data: dict,
    *,
    api_key: str,
    model: str = "qwen3.5-plus",
    base_url: str = "https://coding.dashscope.aliyuncs.com/v1",
    fallback_model: str | None = None,
    fallback_base_url: str | None = None,
    fallback_api_key: str | None = None,
    max_retries: int = 3,
) -> str:
    """Call the LLM to remix feed data into a Chinese digest.

    Tries the primary model up to *max_retries* times, then falls back to
    the fallback model (if configured), and finally to a structured Chinese
    summary on total failure.
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

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # ── Primary model: try max_retries times ──
    for attempt in range(1, max_retries + 1):
        print(f"[ai_builders] LLM attempt {attempt}/{max_retries} with {model}...")
        result = _call_llm(
            messages=messages,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
        if result:
            return result
        print(f"[ai_builders] Primary model attempt {attempt}/{max_retries} failed")

    # ── Fallback model: try once ──
    if fallback_model and fallback_api_key:
        fb_url = fallback_base_url or base_url
        print(f"[ai_builders] Trying fallback model: {fallback_model} @ {fb_url}")
        result = _call_llm(
            messages=messages,
            api_key=fallback_api_key,
            model=fallback_model,
            base_url=fb_url,
            timeout=300.0,  # Extra generous timeout for fallback
        )
        if result:
            print(f"[ai_builders] Fallback model {fallback_model} succeeded!")
            return result
        print(f"[ai_builders] Fallback model {fallback_model} also failed")

    print(f"[ai_builders] All LLM attempts failed, using fallback summary")
    return _fallback_summary(x_items, podcast_items, blog_items)


def _fallback_summary(
    x_items: list[dict],
    podcast_items: list[dict],
    blog_items: list[dict],
) -> str:
    """Generate a structured Chinese summary without LLM.

    This runs when the LLM is unreachable.  Output is in Chinese with
    section headers so readers can still get value from the digest.
    """
    lines: list[str] = []

    if x_items:
        lines.append("## 📱 X / Twitter 动态")
        lines.append("")
        for builder in x_items:
            name = builder.get("name", "")
            handle = builder.get("handle", "")
            bio = builder.get("bio", "")
            tweets = builder.get("tweets", [])
            if not tweets:
                continue
            role = bio.split("\n")[0] if bio else ""
            header = f"**{name}**" + (f" ({role})" if role else "")
            lines.append(header)
            for tweet in tweets[:2]:
                text = tweet.get("text", "")[:280]
                url = tweet.get("url", "")
                likes = tweet.get("likes", 0)
                prefix = f"❤️{likes} " if likes else ""
                lines.append(f"- {prefix}{text}")
                if url:
                    lines.append(f"  [原文链接]({url})")
            lines.append("")

    if podcast_items:
        lines.append("## 🎙️ 播客")
        lines.append("")
        for ep in podcast_items:
            name = ep.get("name", "")
            title = ep.get("title", "")
            url = ep.get("url", "")
            lines.append(f"**{name}**: {title}")
            if url:
                lines.append(f"[收听链接]({url})")
            lines.append("")

    if blog_items:
        lines.append("## 📝 博客")
        lines.append("")
        for post in blog_items:
            name = post.get("name", "")
            title = post.get("title", "")
            url = post.get("url", "")
            lines.append(f"**{name}**: {title}")
            if url:
                lines.append(f"[阅读全文]({url})")
            lines.append("")

    if not lines:
        return "今日 AI Builder 们没有新动态，明天再来看看！"

    lines.insert(0, "⚠️ *LLM 翻译不可用，以下为原始内容摘要*\n")
    return "\n".join(lines)
