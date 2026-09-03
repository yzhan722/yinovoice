"""Bounded ordered id set. Shared by usage dedup and Qwen cancel suppression."""

from __future__ import annotations

from collections import deque

DEFAULT_ID_WINDOW = 4096


class BoundedIdWindow:
    """Keep the newest ``capacity`` ids. Duplicate add does not grow."""

    def __init__(self, capacity: int = DEFAULT_ID_WINDOW) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._ids: set[str] = set()
        self._order: deque[str] = deque()

    @property
    def capacity(self) -> int:
        return self._capacity

    def add(self, item: str) -> bool:
        if item in self._ids:
            return False
        self._ids.add(item)
        self._order.append(item)
        if len(self._order) > self._capacity:
            expired = self._order.popleft()
            self._ids.discard(expired)
        return True

    def discard(self, item: str) -> None:
        if item not in self._ids:
            return
        self._ids.discard(item)
        try:
            self._order.remove(item)
        except ValueError:
            return

    def __contains__(self, item: object) -> bool:
        return isinstance(item, str) and item in self._ids

    def __len__(self) -> int:
        return len(self._ids)

    def clear(self) -> None:
        self._ids.clear()
        self._order.clear()
