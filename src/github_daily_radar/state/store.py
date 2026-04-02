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

    def _history_path(self) -> Path:
        return self.base_dir / "history.json"

    def read_history(self) -> dict:
        path = self._history_path()
        if not path.exists():
            return {"published": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_history(self, history: dict) -> None:
        path = self._history_path()
        path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    def _append_history_entry(self, entry_date: date, candidate_id: str) -> None:
        history = self.read_history()
        history.setdefault("published", []).append(
            {"candidate_id": candidate_id, "date": entry_date.isoformat()}
        )
        self._write_history(history)

    def detect_bootstrap(self) -> bool:
        history = self.read_history()
        if history.get("published"):
            return False
        daily_dir = self.base_dir / "daily"
        return not any(daily_dir.glob("*.json"))

    def is_in_cooldown(self, candidate_id: str, cooldown_days: int, as_of: date) -> bool:
        history = self.read_history()
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

    def record_published(self, day: date, candidates: list[Candidate]) -> None:
        history = self.read_history()
        published = history.setdefault("published", [])
        for candidate in candidates:
            published.append({"candidate_id": candidate.candidate_id, "date": day.isoformat()})
        self._write_history(history)
