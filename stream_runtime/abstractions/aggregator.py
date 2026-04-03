from __future__ import annotations

from typing import Any, Awaitable, Callable

from .models import TaskOutcome

ResultAggregator = Callable[[list[TaskOutcome]], Awaitable[Any] | Any]
