"""Stable failures that can safely cross the public API boundary."""

from __future__ import annotations

from enum import Enum
from typing import Any


class FailureCode(str, Enum):
    """Machine-readable public failure categories."""

    INVALID_INPUT = "invalid_input"
    CONFIGURATION = "configuration_error"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    RATE_LIMITED = "rate_limited"
    MODEL_OUTPUT_INVALID = "model_output_invalid"
    CANCELLED = "cancelled"
    INTERNAL = "internal_error"


class ResearchFailure(Exception):
    """An operational failure with a safe public representation."""

    def __init__(
        self,
        code: FailureCode,
        public_message: str,
        *,
        retryable: bool = False,
        cause: Exception | None = None,
    ) -> None:
        """Initialize a public failure while retaining its private cause chain."""
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.retryable = retryable
        self.__cause__ = cause

    def public_data(self, correlation_id: str) -> dict[str, Any]:
        """Return error data without provider messages, prompts, or stack traces."""
        return {
            "code": self.code.value,
            "correlation_id": correlation_id,
            "retryable": self.retryable,
        }
