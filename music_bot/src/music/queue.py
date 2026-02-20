from __future__ import annotations

import asyncio
from collections import deque
from typing import Deque, Iterable, TypeVar

T = TypeVar("T")


class AsyncQueue:
    def __init__(self) -> None:
        self._items: Deque[T] = deque()
        self._lock = asyncio.Lock()

    async def push(self, item: T) -> None:
        async with self._lock:
            self._items.append(item)

    async def push_many(self, items: Iterable[T]) -> None:
        async with self._lock:
            self._items.extend(items)

    async def pop_left(self) -> T | None:
        async with self._lock:
            if not self._items:
                return None
            return self._items.popleft()

    async def clear(self) -> None:
        async with self._lock:
            self._items.clear()

    async def snapshot(self) -> list[T]:
        async with self._lock:
            return list(self._items)

    async def __len__(self) -> int:
        async with self._lock:
            return len(self._items)
