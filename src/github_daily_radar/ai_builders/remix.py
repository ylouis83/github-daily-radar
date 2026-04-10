"""Remix AI builder feed into Chinese digest text.

LLM fallback chain:
  1. qwen3.5-plus  (千问)   × 3 retries, 240 s
  2. doubao-seed-2.0-pro (火山) × 1 retry, 300 s
  3. kimi-k2.5     (月之暗面) × 1 retry, 240 s
If ALL full-prompt attempts fail → split into chunks and retry the chain.
Final fallback: structured Chinese template (no LLM).
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

# ─────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────

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

{sections}

请按以下格式输出：
1. 先输出 X/Twitter 部分，每位 Builder 一个段落，所有 Builder 都必须包含
2. 再输出播客部分（如果有）
3. 最后输出博客部分（如果有）

每个内容项必须附上原始 URL。不要跳过任何 Builder。"""

# Prompt for chunk mode — simpler, single-section
CHUNK_SYSTEM_PROMPT = """你是一位专业的 AI 行业内容策展人。将提供的内容整理成简洁的中文摘要。

规则:
- 每位 Builder / 每条内容都必须出现在输出中
- 使用 Builder 的全名和职位，不要用 @handle
- 每条内容必须附上原始链接
- 技术术语保留英文，人名公司名保留英文
- 语气：专业但不死板
- 不要编造任何内容，只使用提供的数据
- 不要使用破折号（—）"""

CHUNK_USER_TEMPLATE = """请将以下内容整理成中文摘要，每个条目都要保留。

{content}"""


# ─────────────────────────────────────────────
# Provider config
# ─────────────────────────────────────────────

@dataclass
class LLMProvider:
    """A single LLM endpoint to try."""
    name: str
    model: str
    base_url: str
    api_key: str
    timeout: float = 240.0
    max_retries: int = 1
    extra_body: dict | None = None  # e.g. {"enable_thinking": False} for kimi


def _build_providers(
    *,
    qwen_api_key: str,
    volc_api_key: str | None,
    primary_model: str,
) -> list[LLMProvider]:
    """Build the ordered list of LLM providers to try."""
    providers = [
        LLMProvider(
            name="千问",
            model=primary_model,
            base_url="https://coding.dashscope.aliyuncs.com/v1",
            api_key=qwen_api_key,
            timeout=240.0,
            max_retries=3,
        ),
    ]
    if volc_api_key:
        providers.append(
            LLMProvider(
                name="火山",
                model="doubao-seed-2.0-pro",
                base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
                api_key=volc_api_key,
                timeout=300.0,
                max_retries=1,
            ),
        )
    providers.append(
        LLMProvider(
            name="月之暗面",
            model="kimi-k2.5",
            base_url="https://coding.dashscope.aliyuncs.com/v1",
            api_key=qwen_api_key,
            timeout=240.0,
            max_retries=1,
            extra_body={"enable_thinking": False},
        ),
    )
    return providers


# ─────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────

def _format_twitter_section(x_items: list[dict]) -> str:
    if not x_items:
        return ""
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
        for tweet in tweets[:3]:
            text = tweet.get("text", "")
            url = tweet.get("url", "")
            likes = tweet.get("likes", 0)
            lines.append(f"- [{likes} likes] {text}")
            if url:
                lines.append(f"  URL: {url}")
        sections.append("\n".join(lines))
    return "## X/Twitter 动态\n\n" + "\n\n".join(sections) if sections else ""


def _format_podcast_section(podcast_items: list[dict]) -> str:
    if not podcast_items:
        return ""
    sections = []
    for ep in podcast_items:
        name = ep.get("name", "")
        title = ep.get("title", "")
        url = ep.get("url", "")
        transcript = ep.get("transcript", "")
        if len(transcript) > 4000:
            transcript = transcript[:4000] + "\n...[truncated]"
        sections.append(f"### {name}: {title}\nURL: {url}\n\nTranscript:\n{transcript}")
    return "## 播客\n\n" + "\n\n".join(sections)


def _format_blog_section(blog_items: list[dict]) -> str:
    if not blog_items:
        return ""
    sections = []
    for post in blog_items:
        name = post.get("name", "")
        title = post.get("title", "")
        url = post.get("url", "")
        content = post.get("content", "")
        if len(content) > 4000:
            content = content[:4000] + "\n...[truncated]"
        sections.append(f"### {name}: {title}\nURL: {url}\n\n{content}")
    return "## 博客\n\n" + "\n\n".join(sections)


def _split_twitter_chunks(x_items: list[dict], chunk_size: int = 5) -> list[list[dict]]:
    """Split Twitter builders into smaller groups."""
    return [x_items[i:i + chunk_size] for i in range(0, len(x_items), chunk_size)]


# ─────────────────────────────────────────────
# Core LLM call
# ─────────────────────────────────────────────

def _call_llm(
    *,
    provider: LLMProvider,
    messages: list[dict],
) -> str | None:
    """Make a single LLM API call. Returns content string or None."""
    body = {
        "model": provider.model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 4096,
    }
    if provider.extra_body:
        body.update(provider.extra_body)

    try:
        with httpx.Client(
            base_url=provider.base_url,
            headers={"Authorization": f"Bearer {provider.api_key}"},
            timeout=provider.timeout,
        ) as client:
            resp = client.post("/chat/completions", json=body)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            if content and content.strip():
                return content.strip()
            print(f"[ai_builders] {provider.name} returned empty content")
            return None
    except Exception as exc:
        print(
            f"[ai_builders] {provider.name} ({provider.model}) failed: "
            f"{type(exc).__name__}: {exc}"
        )
        if hasattr(exc, "response"):
            try:
                print(f"[ai_builders]   HTTP {exc.response.status_code}: {exc.response.text[:500]}")
            except Exception:
                pass
        return None


def _try_providers(
    providers: list[LLMProvider],
    messages: list[dict],
    *,
    label: str = "",
) -> str | None:
    """Try each provider in order, with per-provider retries."""
    for provider in providers:
        for attempt in range(1, provider.max_retries + 1):
            tag = f"[{label}] " if label else ""
            print(
                f"[ai_builders] {tag}{provider.name} "
                f"attempt {attempt}/{provider.max_retries}..."
            )
            result = _call_llm(provider=provider, messages=messages)
            if result:
                return result
    return None


# ─────────────────────────────────────────────
# Main entry
# ─────────────────────────────────────────────

def remix_with_llm(
    feed_data: dict,
    *,
    api_key: str,
    model: str = "qwen3.5-plus",
    fallback_model: str | None = None,
    fallback_base_url: str | None = None,
    fallback_api_key: str | None = None,
    max_retries: int = 3,
) -> str:
    """Call the LLM to remix feed data into a Chinese digest.

    Strategy:
      Phase 1 — Full prompt through provider chain
      Phase 2 — Split into chunks, each through provider chain, then merge
      Phase 3 — Structured Chinese fallback (no LLM)
    """
    x_items = feed_data.get("x", [])
    podcast_items = feed_data.get("podcasts", [])
    blog_items = feed_data.get("blogs", [])

    if not x_items and not podcast_items and not blog_items:
        return "今日 AI Builder 们没有新动态，明天再来看看！"

    providers = _build_providers(
        qwen_api_key=api_key,
        volc_api_key=fallback_api_key,
        primary_model=model,
    )

    # ── Phase 1: Full prompt ──
    print("[ai_builders] Phase 1: trying full prompt...")
    sections = "\n\n".join(
        s for s in [
            _format_twitter_section(x_items),
            _format_podcast_section(podcast_items),
            _format_blog_section(blog_items),
        ] if s
    )
    full_prompt = USER_PROMPT_TEMPLATE.format(sections=sections)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": full_prompt},
    ]

    result = _try_providers(providers, messages, label="full")
    if result:
        print(f"[ai_builders] Phase 1 succeeded ({len(result)} chars)")
        return result

    # ── Phase 2: Chunked prompt ──
    print("[ai_builders] Phase 1 failed. Phase 2: splitting into chunks...")
    chunk_results: list[str] = []

    # Twitter chunks (split into groups of 5 builders)
    if x_items:
        twitter_chunks = _split_twitter_chunks(x_items, chunk_size=5)
        for i, chunk in enumerate(twitter_chunks):
            chunk_section = _format_twitter_section(chunk)
            if not chunk_section:
                continue
            chunk_msg = [
                {"role": "system", "content": CHUNK_SYSTEM_PROMPT},
                {"role": "user", "content": CHUNK_USER_TEMPLATE.format(content=chunk_section)},
            ]
            tag = f"twitter-{i + 1}/{len(twitter_chunks)}"
            r = _try_providers(providers, chunk_msg, label=tag)
            if r:
                chunk_results.append(r)
            else:
                # If LLM fails even for a small chunk, use raw text
                chunk_results.append(_raw_twitter_chunk(chunk))

    # Podcast chunk
    if podcast_items:
        podcast_section = _format_podcast_section(podcast_items)
        chunk_msg = [
            {"role": "system", "content": CHUNK_SYSTEM_PROMPT},
            {"role": "user", "content": CHUNK_USER_TEMPLATE.format(content=podcast_section)},
        ]
        r = _try_providers(providers, chunk_msg, label="podcast")
        if r:
            chunk_results.append(r)
        else:
            chunk_results.append(_raw_podcast(podcast_items))

    # Blog chunk
    if blog_items:
        blog_section = _format_blog_section(blog_items)
        chunk_msg = [
            {"role": "system", "content": CHUNK_SYSTEM_PROMPT},
            {"role": "user", "content": CHUNK_USER_TEMPLATE.format(content=blog_section)},
        ]
        r = _try_providers(providers, chunk_msg, label="blog")
        if r:
            chunk_results.append(r)
        else:
            chunk_results.append(_raw_blog(blog_items))

    if chunk_results:
        merged = "\n\n".join(chunk_results)
        print(f"[ai_builders] Phase 2 assembled {len(chunk_results)} chunks ({len(merged)} chars)")
        return merged

    # ── Phase 3: fallback template ──
    print("[ai_builders] All LLM attempts failed, using fallback template")
    return _fallback_summary(x_items, podcast_items, blog_items)


# ─────────────────────────────────────────────
# Raw / fallback formatters
# ─────────────────────────────────────────────

def _raw_twitter_chunk(builders: list[dict]) -> str:
    """Format a small group of Twitter builders without LLM."""
    lines: list[str] = []
    for builder in builders:
        name = builder.get("name", "")
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
    return "\n".join(lines)


def _raw_podcast(podcast_items: list[dict]) -> str:
    lines = ["## 🎙️ 播客", ""]
    for ep in podcast_items:
        name = ep.get("name", "")
        title = ep.get("title", "")
        url = ep.get("url", "")
        lines.append(f"**{name}**: {title}")
        if url:
            lines.append(f"[收听链接]({url})")
        lines.append("")
    return "\n".join(lines)


def _raw_blog(blog_items: list[dict]) -> str:
    lines = ["## 📝 博客", ""]
    for post in blog_items:
        name = post.get("name", "")
        title = post.get("title", "")
        url = post.get("url", "")
        lines.append(f"**{name}**: {title}")
        if url:
            lines.append(f"[阅读全文]({url})")
        lines.append("")
    return "\n".join(lines)


def _fallback_summary(
    x_items: list[dict],
    podcast_items: list[dict],
    blog_items: list[dict],
) -> str:
    """Generate a structured Chinese summary without LLM."""
    parts: list[str] = ["⚠️ *LLM 翻译不可用，以下为原始内容摘要*\n"]

    if x_items:
        parts.append("## 📱 X / Twitter 动态\n")
        parts.append(_raw_twitter_chunk(x_items))

    if podcast_items:
        parts.append(_raw_podcast(podcast_items))

    if blog_items:
        parts.append(_raw_blog(blog_items))

    if len(parts) == 1:
        return "今日 AI Builder 们没有新动态，明天再来看看！"

    return "\n\n".join(parts)
