from __future__ import annotations

from typing import Any, Awaitable, Callable

ObjectExecutor = Callable[[Any], Awaitable[Any]]
