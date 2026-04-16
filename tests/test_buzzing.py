from github_daily_radar.collectors.buzzing import parse_buzzing_feed


def test_parse_buzzing_feed_filters_for_ai_and_dev_items():
    feed = {
        "title": "Product Hunt 热门",
        "items": [
            {
                "title": "CC-BEEPER - 一款适用于 Claude Code 的浮动式 macOS 页面切换器",
                "summary": "A floating macOS pager for Claude Code",
                "url": "https://www.producthunt.com/r/VFG5QZ4RMQUDYX",
                "date_published": "2026-04-15T19:05:40.336Z",
                "tags": ["Open Source", "Developer Tools", "Artificial Intelligence", "GitHub"],
                "_score": 162,
                "_num_comments": 22,
            },
            {
                "title": "一个普通消费品",
                "summary": "Not relevant",
                "url": "https://example.com/non-tech",
                "date_published": "2026-04-15T19:05:40.336Z",
                "tags": ["Lifestyle"],
                "_score": 10,
                "_num_comments": 0,
            },
        ],
    }

    items = parse_buzzing_feed(feed, source="producthunt")

    assert [item.title for item in items] == ["CC-BEEPER - 一款适用于 Claude Code 的浮动式 macOS 页面切换器"]
    assert items[0].score == 162
    assert items[0].comments == 22
    assert items[0].source == "producthunt"
