from __future__ import annotations


class SectionPipelineError(Exception):
    """Base exception for section-level streaming pipelines."""


class SectionClassificationError(SectionPipelineError):
    """Raised when section classification fails."""


class SectionItemStreamError(SectionPipelineError):
    """Raised when the item streaming stage fails."""


class SectionItemParseError(SectionPipelineError):
    """Raised when the parser encounters an unrecoverable problem."""


class SectionSchedulingError(SectionPipelineError):
    """Raised when scheduling item tasks fails."""


class StructuredAggregationError(SectionPipelineError):
    """Raised when final structured node aggregation fails."""
