# GENERATED from golden-paths-shared/python/items_store.py by scripts/sync-golden-shared.sh: edit the source, not this copy.
"""items_store — the deep contract v2 ItemStore, framework-neutral (B163; shared by every Python golden path, B261).

An item is a plain dict {"id": int, "name": str, "tags": [str]}: each framework validates requests with its own idiom
(Pydantic, DRF serializers, marshmallow, msgspec) and hands the store already-valid values. The in-memory store is
the default, so a path runs with no backend; items_backends.py has the real ones.

SOURCE: golden-paths-shared/python/. Each path holds a synced copy (scripts/sync-golden-shared.sh); a guard fails CI
if a copy drifts. Edit this file, never a copy.
"""
from __future__ import annotations

import itertools
import threading
from typing import Protocol


class ItemStore(Protocol):
    def open(self) -> None: ...
    def close(self) -> None: ...
    def create(self, name: str, tags: list[str]) -> dict: ...
    def get(self, item_id: int) -> dict | None: ...
    def list(self, limit: int, offset: int) -> list[dict]: ...


class InMemoryItemStore:
    """The default store: no backend, so the template runs anywhere."""

    def __init__(self) -> None:
        self._items: dict[int, dict] = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()
        self.closed = False

    def open(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def create(self, name: str, tags: list[str]) -> dict:
        with self._lock:
            item = {"id": next(self._ids), "name": name, "tags": list(tags)}
            self._items[item["id"]] = item
        return dict(item)

    def get(self, item_id: int) -> dict | None:
        found = self._items.get(item_id)
        return dict(found) if found else None

    def list(self, limit: int, offset: int) -> list[dict]:
        return [dict(self._items[k]) for k in sorted(self._items)][offset:offset + limit]
