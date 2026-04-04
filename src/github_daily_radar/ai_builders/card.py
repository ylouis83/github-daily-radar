"""Build Feishu interactive card for AI Builders digest.

Card style matches the GitHub Daily Radar card:
  - column_set stats panel
  - indigo/purple header
  - markdown sections with hr separators
  - footer with date and source info
"""
from __future__ import annotations

from datetime import date


def _truncate(text: str, max_len: int = 100) -> str:
    """Truncate text at a sensible boundary."""
    cleaned = (text or "").strip()
    if len(cleaned) <= max_len:
        return cleaned
    cut = cleaned[:max_len].rstrip()
    for ch in (" ", "。", "，", ".", ",", "；", ";"):
        idx = cut.rfind(ch)
        if idx >= max_len // 2:
            return cut[:idx].rstrip() + "…"
    return cut + "…"


def _build_stats_panel(stats: dict) -> dict:
    """Build a column_set stats overview panel (same style as radar)."""
    builders = stats.get("xBuilders", 0)
    tweets = stats.get("totalTweets", 0)
    podcasts = stats.get("podcastEpisodes", 0)
    blogs = stats.get("blogPosts", 0)

    columns = [
        {
            "tag": "column",
            "width": "weighted",
            "weight": 1,
            "vertical_align": "center",
            "elements": [
                {
                    "tag": "markdown",
                    "text_align": "center",
                    "content": f"**{builders}**\nBuilder",
                }
            ],
        },
        {
            "tag": "column",
            "width": "weighted",
            "weight": 1,
            "vertical_align": "center",
            "elements": [
                {
                    "tag": "markdown",
                    "text_align": "center",
                    "content": f"**{tweets}**\n推文",
                }
            ],
        },
        {
            "tag": "column",
            "width": "weighted",
            "weight": 1,
            "vertical_align": "center",
            "elements": [
                {
                    "tag": "markdown",
                    "text_align": "center",
                    "content": f"**{podcasts}**\n播客",
                }
            ],
        },
    ]

    # Only add blog column if there are blogs
    if blogs > 0:
        columns.append(
            {
                "tag": "column",
                "width": "weighted",
                "weight": 1,
                "vertical_align": "center",
                "elements": [
                    {
                        "tag": "markdown",
                        "text_align": "center",
                        "content": f"**{blogs}**\n博客",
                    }
                ],
            }
        )

    return {
        "tag": "column_set",
        "flex_mode": "bisect",
        "background_style": "grey",
        "horizontal_spacing": "default",
        "columns": columns,
    }


def _render_twitter_section(digest_text: str, x_items: list[dict]) -> str:
    """Extract or render the Twitter section from digest text."""
    # The LLM-remixed text is already formatted; use it directly
    # We just wrap it with a section header
    return digest_text


def _split_digest_sections(digest_text: str) -> dict[str, str]:
    """Split digest text into logical sections for card rendering.

    Tries to identify Twitter/Podcast/Blog boundaries.
    Falls back to displaying everything as one block.
    """
    sections: dict[str, str] = {"twitter": "", "podcast": "", "blog": ""}

    # Common section markers the LLM might use
    podcast_markers = ["## 播客", "## 🎙️", "🎙️ PODCAST", "## Podcast", "---\n\n🎙️", "---\n\n## 播客"]
    blog_markers = ["## 博客", "## 📝", "📝 BLOG", "## Blog", "---\n\n📝", "---\n\n## 博客"]

    text = digest_text.strip()

    podcast_pos = -1
    for marker in podcast_markers:
        pos = text.find(marker)
        if pos > 0 and (podcast_pos < 0 or pos < podcast_pos):
            podcast_pos = pos

    blog_pos = -1
    for marker in blog_markers:
        pos = text.find(marker)
        if pos > 0 and (blog_pos < 0 or pos < blog_pos):
            blog_pos = pos

    if podcast_pos > 0:
        sections["twitter"] = text[:podcast_pos].strip()
        if blog_pos > podcast_pos:
            sections["podcast"] = text[podcast_pos:blog_pos].strip()
            sections["blog"] = text[blog_pos:].strip()
        else:
            sections["podcast"] = text[podcast_pos:].strip()
    elif blog_pos > 0:
        sections["twitter"] = text[:blog_pos].strip()
        sections["blog"] = text[blog_pos:].strip()
    else:
        sections["twitter"] = text

    return sections


def build_ai_builders_card(
    *,
    digest_text: str,
    stats: dict,
    feed_data: dict,
    today: date | None = None,
) -> dict:
    """Build a Feishu interactive card for the AI Builders digest.

    Matches the GitHub Daily Radar card style:
    - Purple header with title and date
    - Stats panel (column_set)
    - Content sections separated by hr
    - Footer
    """
    date_str = today.isoformat() if today else ""
    elements: list[dict] = []

    # ── Stats Panel ──
    elements.append(_build_stats_panel(stats))
    elements.append({"tag": "hr"})

    # ── Content Sections ──
    sections = _split_digest_sections(digest_text)

    # Twitter section
    twitter_content = sections.get("twitter", "").strip()
    if twitter_content:
        elements.append({
            "tag": "markdown",
            "content": f"**📱 X / Twitter**\n\n{twitter_content}",
        })
        elements.append({"tag": "hr"})

    # Blog section (before podcast — matching digest-intro.md order)
    blog_content = sections.get("blog", "").strip()
    if blog_content:
        elements.append({
            "tag": "markdown",
            "content": blog_content,
        })
        elements.append({"tag": "hr"})

    # Podcast section
    podcast_content = sections.get("podcast", "").strip()
    if podcast_content:
        elements.append({
            "tag": "markdown",
            "content": podcast_content,
        })
        elements.append({"tag": "hr"})

    # If no sections were split, just show everything
    if not twitter_content and not podcast_content and not blog_content:
        elements.append({
            "tag": "markdown",
            "content": digest_text,
        })
        elements.append({"tag": "hr"})

    # ── Footer ──
    feed_time = stats.get("feedGeneratedAt", "")
    source_note = "数据源：Follow Builders (github.com/zarazhangrui/follow-builders)"
    footer = f"📅 {date_str}  ·  {source_note}"
    elements.append({
        "tag": "markdown",
        "content": footer,
        "text_size": "notation",
    })

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🔭 AI Builders 日报 · {date_str}",
                },
                "template": "purple",
            },
            "elements": elements,
        },
    }
