from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from github_daily_radar.models import Candidate


@dataclass
class StateStore:
    base_dir: Path

    def __post_init__(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        (self.base_dir / "daily").mkdir(parents=True, exist_ok=True)
        (self.base_dir / "cache").mkdir(parents=True, exist_ok=True)

    def _default_history(self) -> dict:
        return {"published": [], "candidate_index": {}, "run_summaries": []}

    def _history_path(self) -> Path:
        return self.base_dir / "history.json"

    def _history_jsonl_path(self) -> Path:
        return self.base_dir / "history.jsonl"

    def read_history(self) -> dict:
        path = self._history_path()
        if not path.exists():
            return self._default_history()
        history = json.loads(path.read_text(encoding="utf-8"))
        history.setdefault("published", [])
        history.setdefault("candidate_index", {})
        history.setdefault("run_summaries", [])
        return history

    def _write_history(self, history: dict) -> None:
        path = self._history_path()
        path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    def _append_history_line(self, record: dict) -> None:
        path = self._history_jsonl_path()
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False))
            fh.write("\n")

    def _append_history_entry(
        self,
        entry_date: date,
        candidate_id: str,
        *,
        metrics: dict | None = None,
        scores: dict | None = None,
        event: str = "published",
        kind: str | None = None,
        title: str | None = None,
        url: str | None = None,
        source_query: str | None = None,
    ) -> None:
        history = self.read_history()
        record = {"candidate_id": candidate_id, "date": entry_date.isoformat(), "event": event}
        if metrics is not None:
            record["metrics"] = metrics
        if scores is not None:
            record["scores"] = scores
        if kind is not None:
            record["kind"] = kind
        if title is not None:
            record["title"] = title
        if url is not None:
            record["url"] = url
        if source_query is not None:
            record["source_query"] = source_query

        self._append_history_line(record)

        if event == "published":
            history.setdefault("published", []).append(record)
        index = history.setdefault("candidate_index", {}).setdefault(candidate_id, {"candidate_id": candidate_id})
        if event == "seen":
            index["last_seen_at"] = entry_date.isoformat()
            if metrics is not None:
                index["last_seen_metrics"] = metrics
            if scores is not None:
                index["last_seen_scores"] = scores
        elif event == "published":
            index["last_published_at"] = entry_date.isoformat()
            if metrics is not None:
                index["last_published_metrics"] = metrics
            if scores is not None:
                index["last_published_scores"] = scores
        self._write_history(history)

    def detect_bootstrap(self) -> bool:
        history = self.read_history()
        if history.get("published"):
            return False
        daily_dir = self.base_dir / "daily"
        return not any(daily_dir.glob("*.json"))

    def is_in_cooldown(self, candidate_id: str, cooldown_days: int, as_of: date) -> bool:
        history = self.read_history()
        index = history.get("candidate_index", {}).get(candidate_id, {})
        if index.get("last_published_at"):
            try:
                published_date = datetime.fromisoformat(index["last_published_at"]).date()
            except ValueError:
                published_date = None
            if published_date and (as_of - published_date).days < cooldown_days:
                return True
        for entry in history.get("published", []):
            if entry.get("candidate_id") != candidate_id:
                continue
            try:
                published_date = datetime.fromisoformat(entry["date"]).date()
            except ValueError:
                continue
            if (as_of - published_date).days < cooldown_days:
                return True
        return False

    def write_daily_state(self, day: str, payload: dict) -> Path:
        daily_path = self.base_dir / "daily" / f"{day}.json"
        daily_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return daily_path

    def record_run_summary(self, day: date, summary: dict) -> None:
        history = self.read_history()
        history.setdefault("run_summaries", []).append({"date": day.isoformat(), **summary})
        self._append_history_line({"candidate_id": "__run_summary__", "date": day.isoformat(), "event": "run_summary", "summary": summary})
        self._write_history(history)

    def record_seen(self, day: date, candidates: list[Candidate]) -> None:
        for candidate in candidates:
            self._append_history_entry(
                day,
                candidate.candidate_id,
                metrics=candidate.metrics.model_dump(),
                scores=dict(candidate.rule_scores),
                event="seen",
                kind=candidate.kind,
                title=candidate.title,
                url=candidate.url,
                source_query=candidate.source_query,
            )

    def record_published(self, day: date, candidates: list[Candidate]) -> None:
        for candidate in candidates:
            if isinstance(candidate, Candidate):
                candidate_id = candidate.candidate_id
                metrics = candidate.metrics.model_dump()
                scores = dict(candidate.rule_scores)
                kind = candidate.kind
                title = candidate.title
                url = candidate.url
                source_query = candidate.source_query
            else:
                candidate_id = candidate.get("candidate_id") or f"{candidate.get('kind', 'item')}:{candidate.get('repo_full_name') or candidate.get('url') or candidate.get('title')}"
                metrics = candidate.get("metrics")
                scores = candidate.get("rule_scores") or candidate.get("scores") or {}
                kind = candidate.get("kind")
                title = candidate.get("title")
                url = candidate.get("url")
                source_query = candidate.get("source_query")
            self._append_history_entry(
                day,
                candidate_id,
                metrics=metrics,
                scores=scores,
                event="published",
                kind=kind,
                title=title,
                url=url,
                source_query=source_query,
            )
