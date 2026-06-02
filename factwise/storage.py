from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

from django.conf import settings


class JSONStorage:
    # map filename -> Lock so each JSON file has its own write lock
    _locks: dict[str, Lock] = {}
    # protect the locks registry from concurrent updates
    _registry_lock = Lock()

    @classmethod
    def _get_lock(cls, filename: str) -> Lock:
        with cls._registry_lock:
            lock = cls._locks.get(filename)
            if lock is None:
                lock = Lock()
                cls._locks[filename] = lock
            return lock

    @staticmethod
    def _resolve_path(filename: str) -> Path:
        normalized = filename if filename.endswith('.json') else f'{filename}.json'
        # Build the path to the JSON file using the configured DB_DIR when available.
        # This keeps all persistence under one configured folder (easy to change).
        base = getattr(settings, 'DB_DIR', None) or (Path(settings.BASE_DIR) / 'db')
        return Path(base) / normalized

    def load(self, filename: str) -> dict[str, Any]:
        path = self._resolve_path(filename)
        lock = self._get_lock(path.name)
        with lock:
            if not path.exists():
                return {}
            with path.open('r', encoding='utf-8') as handle:
                return json.load(handle)

    def save(self, filename: str, data: dict[str, Any]) -> None:
        path = self._resolve_path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = self._get_lock(path.name)
        with lock:
            with path.open('w', encoding='utf-8') as handle:
                json.dump(data, handle, indent=2)
