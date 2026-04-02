from collections import defaultdict


def group_digest_items(items: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        grouped[item.get("kind", "other")].append(item)

    ordered_kinds = ["project", "skill", "discussion", "issue", "pr", "other"]
    sections: list[dict] = []
    for kind in ordered_kinds:
        if kind in grouped:
            sections.append({"title": kind.title(), "items": grouped[kind]})
    return sections
