from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from github_daily_radar.collectors.buzzing import SOURCE_LABELS
from github_daily_radar.models import BuilderSignal, Candidate, ExternalTechCandidate

_GITHUB_URL_REPO_REF_RE = re.compile(r"https?://(?:www\.)?github\.com/([A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]+)")
_TOKEN_RE = re.compile(r"[A-Za-z0-9_.-]+")
_GENERIC_REPO_ALIASES = {
    "agent",
    "agents",
    "app",
    "assistant",
    "build",
    "builder",
    "cli",
    "code",
    "project",
    "prompt",
    "repo",
    "server",
    "skill",
    "skills",
    "tool",
    "tools",
    "workflow",
}
_LOW_SIGNAL_MAINTAINERS = {
    "github",
    "open-source",
    "opensource",
    "oss",
    "sponsors",
}
_NON_REPO_OWNERS = {
    "blog",
    "blogs",
    "post",
    "posts",
    "status",
    "topic",
    "topics",
    "video",
    "videos",
    "watch",
    "www",
}


@dataclass(frozen=True)
class RadarEnrichment:
    candidates: list[Candidate]
    tech_matches: dict[str, dict]
    builder_matches: dict[str, dict]
    maintainer_items: list[dict]
    cluster_count: int


def _slug(text: str) -> str:
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", str(text or "").lower())
    return lowered.strip("-")


def _candidate_source_label(candidate: Candidate) -> str:
    raw_signals = candidate.raw_signals or {}
    if raw_signals.get("trending_item"):
        return "Trending"
    if raw_signals.get("ossinsight_item"):
        return "OSSInsight"
    if raw_signals.get("code_search_item"):
        return "Skill Search"
    if raw_signals.get("graphql_item") or raw_signals.get("seed_repo"):
        return "Seed Repo"
    if candidate.kind == "discussion":
        return "Discussions"
    if candidate.kind in {"issue", "pr"}:
        return "Issues / PRs"
    return "GitHub Search"


def _tech_source_label(candidate: ExternalTechCandidate) -> str:
    return SOURCE_LABELS.get(candidate.source, candidate.source)


def _builder_source_label(signal: BuilderSignal) -> str:
    if signal.section == "x":
        return "Builder X"
    if signal.section == "podcast":
        return "Builder Podcast"
    if signal.section == "blog":
        return "Builder Blog"
    return signal.section


def _repo_aliases(repo_full_name: str, title: str = "") -> list[str]:
    aliases: list[str] = []
    if "/" in repo_full_name:
        owner, repo = repo_full_name.lower().split("/", 1)
        aliases.append(repo_full_name.lower())
        if len(repo) >= 4 and repo not in _GENERIC_REPO_ALIASES:
            aliases.append(repo)
        if title and title.lower() != repo_full_name.lower():
            aliases.append(title.lower())
        if owner and len(owner) >= 4:
            aliases.append(f"{owner}/{repo}")
    return list(dict.fromkeys(alias for alias in aliases if alias))


def _extract_repo_refs(*parts: str) -> list[str]:
    refs: list[str] = []
    for part in parts:
        if not isinstance(part, str) or not part.strip():
            continue
        for match in _GITHUB_URL_REPO_REF_RE.findall(part):
            normalized = match.lower().strip(" /")
            if _is_probable_repo_ref(normalized):
                refs.append(normalized)
    return list(dict.fromkeys(ref for ref in refs if "/" in ref))


def _is_probable_repo_ref(ref: str) -> bool:
    if "/" not in ref:
        return False
    owner, repo = ref.split("/", 1)
    owner = owner.strip().lower()
    repo = repo.strip().lower()
    if not owner or not repo or "." in owner or owner in _NON_REPO_OWNERS:
        return False
    if not any(char.isalpha() for char in repo):
        return False
    return True


def _match_aliases(text: str, alias_index: dict[str, set[str]]) -> set[str]:
    if not text.strip():
        return set()
    lowered = text.lower()
    token_set = {token.lower() for token in _TOKEN_RE.findall(lowered)}
    matched: set[str] = set()
    for alias, entity_keys in alias_index.items():
        if not alias:
            continue
        if "/" in alias or " " in alias:
            if alias in lowered:
                matched.update(entity_keys)
        elif alias in token_set:
            matched.update(entity_keys)
    return matched


def _entity_key_for_repo(repo_full_name: str) -> str:
    return f"repo:{repo_full_name.lower()}"


def _maintainer_name(candidate: Candidate) -> str:
    if "/" in candidate.repo_full_name:
        return candidate.repo_full_name.split("/", 1)[0]
    return candidate.author or ""


def _annotate_candidate(candidate: Candidate) -> Candidate:
    repo_full_name = candidate.repo_full_name.lower().strip()
    entity_key = _entity_key_for_repo(repo_full_name) if repo_full_name else f"topic:{_slug(candidate.title)}"
    maintainer_name = _maintainer_name(candidate).strip()
    maintainer_key = f"person:{_slug(maintainer_name)}" if maintainer_name else ""
    raw_signals = {
        **candidate.raw_signals,
        "entity_key": entity_key,
        "entity_aliases": _repo_aliases(candidate.repo_full_name, candidate.title),
        "maintainer_key": maintainer_key,
        "maintainer_name": maintainer_name,
        "source_label": _candidate_source_label(candidate),
    }
    return candidate.model_copy(update={"raw_signals": raw_signals})


def _build_alias_indexes(candidates: list[Candidate]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    entity_alias_index: dict[str, set[str]] = defaultdict(set)
    maintainer_alias_index: dict[str, set[str]] = defaultdict(set)
    for candidate in candidates:
        raw_signals = candidate.raw_signals or {}
        entity_key = str(raw_signals.get("entity_key") or "").strip()
        for alias in raw_signals.get("entity_aliases", []):
            if isinstance(alias, str) and alias.strip():
                entity_alias_index[alias.lower()].add(entity_key)
        maintainer_name = str(raw_signals.get("maintainer_name") or "").strip().lower()
        maintainer_key = str(raw_signals.get("maintainer_key") or "").strip()
        if maintainer_name and maintainer_key:
            maintainer_alias_index[maintainer_name].add(maintainer_key)
    return entity_alias_index, maintainer_alias_index


def _empty_cluster() -> dict:
    return {
        "repo_full_name": "",
        "titles": set(),
        "candidate_ids": set(),
        "source_labels": set(),
        "kind_labels": set(),
        "github_candidates": 0,
        "tech_hits": 0,
        "builder_hits": 0,
    }


def _resolve_external_item(
    *,
    title: str,
    url: str,
    summary: str,
    entity_alias_index: dict[str, set[str]],
) -> dict:
    direct_repos = _extract_repo_refs(title, url, summary)
    entity_keys = {_entity_key_for_repo(repo) for repo in direct_repos}
    alias_text = " ".join(part for part in (title, summary, url) if part)
    entity_keys.update(_match_aliases(alias_text, entity_alias_index))
    matched_repos = sorted(key.split("repo:", 1)[-1] for key in entity_keys if key.startswith("repo:"))
    return {
        "entity_keys": sorted(entity_keys),
        "matched_repos": matched_repos,
    }


def _resolve_builder_signal(
    signal: BuilderSignal,
    *,
    entity_alias_index: dict[str, set[str]],
    maintainer_alias_index: dict[str, set[str]],
) -> dict:
    entity_match = _resolve_external_item(
        title=signal.title,
        url=signal.url,
        summary=" ".join(part for part in (signal.creator, signal.summary) if part),
        entity_alias_index=entity_alias_index,
    )
    maintainer_keys = _match_aliases(" ".join(part for part in (signal.creator, signal.title, signal.summary) if part), maintainer_alias_index)
    return {
        **entity_match,
        "maintainer_keys": sorted(maintainer_keys),
    }


def _cluster_payload(cluster: dict) -> dict:
    return {
        "repo_full_name": cluster["repo_full_name"],
        "source_labels": sorted(cluster["source_labels"]),
        "kind_labels": sorted(cluster["kind_labels"]),
        "github_candidates": int(cluster["github_candidates"]),
        "tech_hits": int(cluster["tech_hits"]),
        "builder_hits": int(cluster["builder_hits"]),
        "titles": sorted(cluster["titles"])[:4],
    }


def _build_maintainer_items(
    candidates: list[Candidate],
    *,
    clusters: dict[str, dict],
    builder_matches: dict[str, dict],
) -> tuple[list[dict], dict[str, dict]]:
    grouped: dict[str, dict] = {}
    for candidate in candidates:
        raw_signals = candidate.raw_signals or {}
        maintainer_key = str(raw_signals.get("maintainer_key") or "").strip()
        maintainer_name = str(raw_signals.get("maintainer_name") or "").strip()
        if (
            not maintainer_key
            or not maintainer_name
            or maintainer_name.lower() in _GENERIC_REPO_ALIASES
            or maintainer_name.lower() in _LOW_SIGNAL_MAINTAINERS
        ):
            continue
        group = grouped.setdefault(
            maintainer_key,
            {
                "display_name": maintainer_name,
                "repos": {},
                "source_labels": set(),
                "builder_hits": 0,
                "candidate_count": 0,
                "url": f"https://github.com/{maintainer_name}",
            },
        )
        group["candidate_count"] += 1
        repo_full_name = candidate.repo_full_name
        if repo_full_name and repo_full_name not in group["repos"]:
            group["repos"][repo_full_name] = {
                "title": candidate.title,
                "star_growth": max(int(candidate.metrics.star_growth_7d or 0), 0),
            }
        cluster = clusters.get(str(raw_signals.get("entity_key") or "")) or {}
        group["source_labels"].update(cluster.get("source_labels", set()))

    for match in builder_matches.values():
        for maintainer_key in match.get("maintainer_keys", []):
            group = grouped.get(maintainer_key)
            if group is not None:
                group["builder_hits"] += 1

    maintainer_profiles: dict[str, dict] = {}
    maintainer_items: list[dict] = []

    for maintainer_key, payload in grouped.items():
        repo_names = sorted(
            payload["repos"],
            key=lambda repo: payload["repos"][repo]["star_growth"],
            reverse=True,
        )
        repo_count = len(repo_names)
        source_labels = sorted(payload["source_labels"])
        if repo_count < 2 and len(source_labels) < 3 and payload["builder_hits"] <= 0:
            continue

        top_repos = repo_names[:2]
        source_summary = " / ".join(source_labels[:3])
        repo_summary = "、".join(top_repos)
        title = (
            f"{payload['display_name']}：{repo_count} 个仓库同时冒头"
            if repo_count >= 2
            else f"{payload['display_name']}：近期持续活跃"
        )
        why_now_parts = []
        if repo_summary:
            why_now_parts.append(f"关注 {repo_summary}")
        if source_summary:
            why_now_parts.append(f"信号来自 {source_summary}")
        if payload["builder_hits"] > 0:
            why_now_parts.append("并被 Builder Watch 提到")
        why_now = "，".join(why_now_parts).strip("，")
        score = repo_count * 2.5 + len(source_labels) * 1.2 + payload["builder_hits"] * 1.5 + payload["candidate_count"] * 0.5

        maintainer_profiles[maintainer_key] = {
            "repo_count": repo_count,
            "source_labels": source_labels,
            "builder_hits": payload["builder_hits"],
            "display_name": payload["display_name"],
        }
        maintainer_items.append(
            {
                "title": title,
                "url": payload["url"],
                "creator": payload["display_name"],
                "summary": why_now,
                "why_now": why_now,
                "score": score,
                "source": "github",
                "source_label": "GitHub",
            }
        )

    maintainer_items.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    return maintainer_items[:3], maintainer_profiles


def enrich_radar_context(
    *,
    candidates: list[Candidate],
    tech_candidates: list[ExternalTechCandidate],
    builder_signals: list[BuilderSignal],
) -> RadarEnrichment:
    annotated_candidates = [_annotate_candidate(candidate) for candidate in candidates]
    entity_alias_index, maintainer_alias_index = _build_alias_indexes(annotated_candidates)

    clusters: dict[str, dict] = defaultdict(_empty_cluster)
    for candidate in annotated_candidates:
        raw_signals = candidate.raw_signals or {}
        entity_key = str(raw_signals.get("entity_key") or "").strip()
        if not entity_key:
            continue
        cluster = clusters[entity_key]
        cluster["repo_full_name"] = candidate.repo_full_name or cluster["repo_full_name"]
        cluster["titles"].add(candidate.title)
        cluster["candidate_ids"].add(candidate.candidate_id)
        cluster["source_labels"].add(str(raw_signals.get("source_label") or _candidate_source_label(candidate)))
        cluster["kind_labels"].add(candidate.kind)
        cluster["github_candidates"] += 1

    tech_matches: dict[str, dict] = {}
    for tech_candidate in tech_candidates:
        match = _resolve_external_item(
            title=tech_candidate.title,
            url=tech_candidate.url,
            summary=tech_candidate.summary,
            entity_alias_index=entity_alias_index,
        )
        tech_matches[tech_candidate.url] = match
        for entity_key in match["entity_keys"]:
            cluster = clusters[entity_key]
            cluster["repo_full_name"] = match["matched_repos"][0] if match["matched_repos"] else cluster["repo_full_name"]
            cluster["source_labels"].add(_tech_source_label(tech_candidate))
            cluster["titles"].add(tech_candidate.title)
            cluster["tech_hits"] += 1

    builder_matches: dict[str, dict] = {}
    for signal in builder_signals:
        match = _resolve_builder_signal(
            signal,
            entity_alias_index=entity_alias_index,
            maintainer_alias_index=maintainer_alias_index,
        )
        builder_matches[signal.url] = match
        for entity_key in match["entity_keys"]:
            cluster = clusters[entity_key]
            cluster["repo_full_name"] = match["matched_repos"][0] if match["matched_repos"] else cluster["repo_full_name"]
            cluster["source_labels"].add(_builder_source_label(signal))
            cluster["titles"].add(signal.title)
            cluster["builder_hits"] += 1

    for url, match in builder_matches.items():
        cluster_sources: set[str] = set()
        for entity_key in match.get("entity_keys", []):
            cluster_sources.update(clusters.get(entity_key, {}).get("source_labels", set()))
        builder_matches[url] = {
            **match,
            "cluster_sources": sorted(cluster_sources),
        }

    maintainer_items, maintainer_profiles = _build_maintainer_items(
        annotated_candidates,
        clusters=clusters,
        builder_matches=builder_matches,
    )

    enriched_candidates: list[Candidate] = []
    for candidate in annotated_candidates:
        raw_signals = dict(candidate.raw_signals)
        entity_key = str(raw_signals.get("entity_key") or "").strip()
        cluster = clusters.get(entity_key) or _empty_cluster()
        maintainer_profile = maintainer_profiles.get(str(raw_signals.get("maintainer_key") or "").strip(), {})
        raw_signals["cluster"] = _cluster_payload(cluster)
        if maintainer_profile:
            raw_signals["maintainer_activity"] = maintainer_profile
        rule_scores = {
            **candidate.rule_scores,
            "cluster_source_count": float(len(cluster["source_labels"])),
            "cluster_candidate_count": float(len(cluster["candidate_ids"])),
            "cluster_builder_hits": float(cluster["builder_hits"]),
            "cluster_tech_hits": float(cluster["tech_hits"]),
            "maintainer_repo_count": float(maintainer_profile.get("repo_count", 0)),
        }
        enriched_candidates.append(candidate.model_copy(update={"raw_signals": raw_signals, "rule_scores": rule_scores}))

    return RadarEnrichment(
        candidates=enriched_candidates,
        tech_matches=tech_matches,
        builder_matches=builder_matches,
        maintainer_items=maintainer_items,
        cluster_count=len(clusters),
    )
