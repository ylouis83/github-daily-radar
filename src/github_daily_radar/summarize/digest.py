from collections import defaultdict


def group_digest_items(items: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        grouped[item.get("kind", "other")].append(item)

    def sort_key(item: dict) -> tuple[int, int]:
        rank = item.get("editorial_rank")
        if rank is None:
            return (1, 0)
        return (0, int(rank))

    ordered_kinds = ["project", "skill", "discussion", "issue", "pr", "other"]
    sections: list[dict] = []
    for kind in ordered_kinds:
        if kind in grouped:
            sections.append({"title": kind.title(), "items": sorted(grouped[kind], key=sort_key)})
    return sections
