class StreamRuntimeError(Exception):
    """Base exception for stream runtime."""


class SourceStreamError(StreamRuntimeError):
    """Raised when upstream chunk source fails."""


class ParserError(StreamRuntimeError):
    """Raised when parser fails in a fatal way."""


class SchedulerClosedError(StreamRuntimeError):
    """Raised when adding tasks to a closed scheduler."""


class AggregationError(StreamRuntimeError):
    """Raised when aggregator fails."""
