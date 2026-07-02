from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from config import STATE_PATH, backup_corrupt_file, write_json


DEFAULT_STATE: dict[str, Any] = {
    "last_checked_at": None,
    "last_notified_post_id": None,
    "last_notified_at": None,
    "last_post_published_at": None,
    "last_permalink": None,
    "last_image_path": None,
    "last_result": None,
    "last_error": None,
}


class StateStore:
    def __init__(self, path: Path = STATE_PATH) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            self.save(DEFAULT_STATE.copy())
            return DEFAULT_STATE.copy()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            backup_corrupt_file(self.path)
            self.save(DEFAULT_STATE.copy())
            return DEFAULT_STATE.copy()
        state = DEFAULT_STATE.copy()
        if isinstance(data, dict):
            state.update({key: data.get(key) for key in DEFAULT_STATE})
        return state

    def save(self, state: dict[str, Any]) -> None:
        clean = DEFAULT_STATE.copy()
        clean.update({key: state.get(key) for key in DEFAULT_STATE})
        write_json(self.path, clean)

    def update(self, **values: Any) -> dict[str, Any]:
        state = self.load()
        state.update(values)
        self.save(state)
        return state


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
