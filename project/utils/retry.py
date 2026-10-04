"""
Centralized retry policy module matching Section 11 of Technical Implementation Plan.
Enforces bounded exponential retries for transient failures.
"""
import asyncio
from typing import Callable, TypeVar, Awaitable, Tuple, Type, Optional
from project.utils.logging import logger
from project.utils.exceptions import TimeoutError, NetworkError, HTTPError

T = TypeVar("T")

# Transient exceptions eligible for bounded retry
RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    TimeoutError,
    NetworkError,
    asyncio.TimeoutError,
    ConnectionResetError,
    ConnectionError,
)


def is_retryable_status_code(status_code: int) -> bool:
    """
    Classifies HTTP status codes according to Section 11 & Section 18.
    5xx server errors and 429 Too Many Requests are retryable.
    4xx client errors (400, 401, 403, 404, 422) are non-retryable.
    """
    return status_code in (429, 500, 502, 503, 504)


async def execute_with_retry(
    operation: Callable[[int], Awaitable[T]],
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 30.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = RETRYABLE_EXCEPTIONS,
) -> T:
    """
    Executes an async callable with bounded retries and exponential backoff.
    
    Args:
        operation: Async callable taking the 1-indexed attempt number as argument.
        max_retries: Maximum number of retries (0 = 1 attempt total, no retry).
        base_delay: Delay before the first retry in seconds (default 1.0s).
        backoff_factor: Multiplier for subsequent delays (default 2.0).
        max_delay: Cap for backoff delay in seconds.
        retryable_exceptions: Tuple of exception types that should trigger retry.

    Returns:
        The result of the operation callable.

    Raises:
        The exception raised by the last failed attempt if retries are exhausted
        or if a non-retryable exception is encountered.
    """
    attempt = 1
    total_attempts = max_retries + 1

    while True:
        try:
            return await operation(attempt)
        except Exception as exc:
            # Check if this exception is retryable
            is_retryable = isinstance(exc, retryable_exceptions)
            if isinstance(exc, HTTPError) and hasattr(exc, "status_code"):
                is_retryable = is_retryable_status_code(exc.status_code)

            if not is_retryable or attempt >= total_attempts:
                if attempt >= total_attempts:
                    logger.warning(
                        f"Retries exhausted ({attempt}/{total_attempts}) for operation: {exc}"
                    )
                raise exc

            # Calculate delay: base_delay * (backoff_factor ** (attempt - 1))
            delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)
            logger.warning(
                f"Attempt {attempt}/{total_attempts} failed with {type(exc).__name__}: {exc}. "
                f"Retrying in {delay:.2f}s..."
            )
            await asyncio.sleep(delay)
            attempt += 1
