from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from github_daily_radar.publish.feishu import build_digest_card, build_style_review_card, send_cards


def _preview_today() -> date:
    timezone_name = os.getenv("TIMEZONE", "Asia/Shanghai")
    return datetime.now(ZoneInfo(timezone_name)).date()


def build_preview_cards(*, today: date | None = None, style_only: bool = False) -> list[dict]:
    current_day = today or _preview_today()
    if style_only:
        return [build_style_review_card(today=current_day)]

    card = build_digest_card(
        items=[
            {
                "kind": "project",
                "title": "anthropics/claude-code-desktop",
                "url": "https://github.com/anthropics/claude-code-desktop",
                "trait": "桌面端多会话协作的 AI 编程工作台",
                "capability": "把并行 agent、文件拖拽和上下文切换收进统一工作流",
                "necessity": "适合把 AI coding 从单轮对话升级为持续开发环境",
                "why_now": "桌面 redesign 刚发布，Builder 生态讨论很集中",
                "stars": 18400,
                "star_delta_1d": 1240,
                "star_velocity": "surge",
                "repo_full_name": "anthropics/claude-code-desktop",
            },
            {
                "kind": "project",
                "title": "openai/agents-sdk-examples",
                "url": "https://github.com/openai/agents-sdk-examples",
                "trait": "围绕 agent orchestration 的实战样例仓库",
                "capability": "覆盖工具调用、多代理分工和生产级 workflow 组合",
                "necessity": "适合团队快速建立 agent 产品的工程基线",
                "why_now": "样例和社区二创都在加速扩张",
                "stars": 9600,
                "star_delta_1d": 410,
                "star_velocity": "surge",
                "repo_full_name": "openai/agents-sdk-examples",
            },
            {
                "kind": "project",
                "title": "microsoft/mcp-toolkit",
                "url": "https://github.com/microsoft/mcp-toolkit",
                "trait": "MCP 服务与客户端集成的参考工具箱",
                "capability": "帮助团队更快搭建协议接入层和调试链路",
                "necessity": "适合正在把工具生态接到 agent 工作流里的团队",
                "why_now": "MCP 相关搜索与上手需求持续抬升",
                "stars": 7200,
                "star_delta_1d": 180,
                "star_velocity": "rising",
                "repo_full_name": "microsoft/mcp-toolkit",
            },
            {
                "kind": "project",
                "title": "vercel/ai-chatbot",
                "url": "https://github.com/vercel/ai-chatbot",
                "trait": "产品化 AI 对话应用的快速起步模板",
                "capability": "把前端界面、模型接入和部署路径串成一条线",
                "necessity": "适合验证新交互和新模型能力的落地速度",
                "why_now": "模板类项目重新升温，团队更关注交付速度",
                "stars": 14800,
                "star_delta_1d": 92,
                "star_velocity": "rising",
                "repo_full_name": "vercel/ai-chatbot",
            },
            {
                "kind": "project",
                "title": "langgenius/dify",
                "url": "https://github.com/langgenius/dify",
                "trait": "把 AI 应用编排、RAG 和 workflow 组织成可运营平台",
                "capability": "兼顾产品配置体验和团队协作所需的基础设施",
                "necessity": "适合做企业内 AI 应用平台和 demo 中台",
                "why_now": "平台型产品重新升温，大家更关心落地和运营效率",
                "stars": 78300,
                "star_delta_1d": 76,
                "star_velocity": "rising",
                "repo_full_name": "langgenius/dify",
            },
            {
                "kind": "project",
                "title": "agno-agi/agno",
                "url": "https://github.com/agno-agi/agno",
                "trait": "围绕 agent memory、tools 和 workflow 的开发框架",
                "capability": "帮助团队快速搭建结构化 agent 应用",
                "necessity": "适合用来展示 agent framework 类项目的卡片样貌",
                "why_now": "agent framework 竞争加速，适合放进主榜预览样本",
                "stars": 22100,
                "star_delta_1d": 64,
                "star_velocity": "rising",
                "repo_full_name": "agno-agi/agno",
            },
            {
                "kind": "project",
                "title": "browser-use/browser-use",
                "url": "https://github.com/browser-use/browser-use",
                "summary": "让 agent 真正接管浏览器任务的热门项目",
                "why_now": "浏览器自动化仍是 agent 落地的核心方向之一",
                "stars": 61200,
                "star_delta_1d": 88,
                "star_velocity": "rising",
                "repo_full_name": "browser-use/browser-use",
            },
            {
                "kind": "skill",
                "title": "ylouis83/claude-code-skills",
                "url": "https://github.com/ylouis83/claude-code-skills",
                "trait": "把个人工作流沉淀为可复用 skills 资产",
                "summary": "适合作为 skill 库和团队协作基线",
                "stars": 5300,
                "repo_full_name": "ylouis83/claude-code-skills",
            },
            {
                "kind": "discussion",
                "title": "RFC: Multi-agent handoff patterns",
                "url": "https://github.com/example/agents/discussions/42",
                "trait": "如何把探索、执行、审查三类 agent 接成稳定流水线",
                "capability": "讨论 handoff 边界、上下文压缩和失败回退策略",
                "necessity": "适合团队在多 agent 协作前先统一工程规则",
                "why_now": "多代理从实验阶段转向工程化阶段",
            },
        ],
        tech_items=[
            {
                "title": "Claude Code Routines",
                "url": "https://www.producthunt.com/r/C2HEOHKNZ3RKQM",
                "source_label": "Product Hunt",
                "why_now": "把日常 Claude Code 任务做成可重复运行的工作例程",
            },
            {
                "title": "The agent orchestration problem nobody talks about",
                "url": "https://dev.to/o96a/the-agent-orchestration-problem-nobody-talks-about-7kp",
                "source_label": "Dev.to",
                "why_now": "点中了多代理系统在工程边界和状态传递上的真实痛点",
            },
            {
                "title": "Porting Mac OS X to Nintendo Wii",
                "url": "https://bryankeller.github.io/2026/04/08/porting-mac-os-x-nintendo-wii.html",
                "source_label": "Hacker News",
                "why_now": "非常强的黑客气质内容，适合做卡片里的外部亮点样本",
            },
        ],
        builder_sections={
            "x": [
                {
                    "title": "Claude",
                    "url": "https://x.com/claudeai/status/2044131493966909862",
                    "creator": "Claude",
                    "why_now": "新桌面版支持多会话管理和更流畅的并行协作体验。",
                },
                {
                    "title": "Swyx",
                    "url": "https://x.com/swyx/status/2044000000000000000",
                    "creator": "Swyx",
                    "why_now": "从 builder 视角解释为什么 agent 产品开始进入“工作台”阶段。",
                },
            ],
            "podcast": [
                {
                    "title": "From SEO to Agent-Led Growth",
                    "url": "https://www.youtube.com/playlist?list=PLOhHNjZItNnMm5tdW61JpnyxeYH5NDDx8",
                    "creator": "Training Data",
                    "why_now": "把增长、内容和 agent workflow 放到同一条叙事线上。",
                }
            ],
            "blog": [
                {
                    "title": "Redesigning Claude Code on desktop for parallel agents",
                    "url": "https://claude.com/blog/claude-code-desktop-redesign",
                    "creator": "Claude Blog",
                    "why_now": "很适合作为 Builder Watch 的编辑式收尾内容。",
                }
            ],
        },
        surge_items=[
            {
                "title": "anthropics/claude-code-desktop",
                "url": "https://github.com/anthropics/claude-code-desktop",
                "repo_full_name": "anthropics/claude-code-desktop",
                "surge_daily_delta": 1240,
                "stars": 18400,
            },
            {
                "title": "browser-use/browser-use",
                "url": "https://github.com/browser-use/browser-use",
                "repo_full_name": "browser-use/browser-use",
                "surge_daily_delta": 980,
                "stars": 61200,
            },
        ],
        metadata={
            "count": 42,
            "item_count": 10,
            "top_themes": ["ai_project", "claude_code", "agent_workflow"],
        },
        today=current_day,
        project_first=True,
    )
    return [card]


def write_preview_artifact(*, cards: list[dict]) -> None:
    output_dir = Path("artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "preview-card.json").write_text(
        json.dumps({"cards": cards}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    style_only = os.getenv("PREVIEW_STYLE_ONLY", "false").lower() == "true"
    cards = build_preview_cards(style_only=style_only)
    write_preview_artifact(cards=cards)

    dry_run = os.getenv("PREVIEW_DRY_RUN", "false").lower() == "true"
    if dry_run:
        return

    webhook_url = os.getenv("FEISHU_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise RuntimeError("FEISHU_WEBHOOK_URL is required for preview sends")

    send_cards(webhook_url=webhook_url, cards=cards)


if __name__ == "__main__":
    main()
