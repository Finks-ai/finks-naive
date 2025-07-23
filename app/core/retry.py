"""
Retry utilities with exponential backoff.
"""

import asyncio
import functools
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, cast

from loguru import logger

T = TypeVar("T")


def exponential_backoff_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for exponential backoff retry logic.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff calculation
        jitter: Add random jitter to prevent thundering herd
        exceptions: Tuple of exception types to catch and retry
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    result = await cast("Callable[..., Awaitable[T]]", func)(*args, **kwargs)
                    return result
                except exceptions as e:
                    last_exception = e

                    if attempt >= max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}. Last error: {e!s}")
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base**attempt), max_delay)

                    # Add jitter if enabled
                    if jitter:
                        delay = delay * (0.5 + random.random())  # nosec B311

                    logger.warning(
                        f"Error in {func.__name__} (attempt {attempt + 1}/{max_retries + 1}): {e!s}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )

                    await asyncio.sleep(delay)

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected state in retry logic")

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt >= max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}. Last error: {e!s}")
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base**attempt), max_delay)

                    # Add jitter if enabled
                    if jitter:
                        delay = delay * (0.5 + random.random())  # nosec B311

                    logger.warning(
                        f"Error in {func.__name__} (attempt {attempt + 1}/{max_retries + 1}): {e!s}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )

                    time.sleep(delay)

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected state in retry logic")

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return cast("Callable[..., T]", async_wrapper)
        else:
            return sync_wrapper

    return decorator


# Convenience decorators for common retry scenarios
def retry_on_error(max_retries: int = 3) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Simple retry decorator with default exponential backoff."""
    return exponential_backoff_retry(
        max_retries=max_retries, base_delay=1.0, max_delay=30.0, exponential_base=2.0, jitter=True
    )


def retry_on_ai_errors(max_retries: int = 3) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry decorator specifically for AI API errors."""
    return exponential_backoff_retry(
        max_retries=max_retries,
        base_delay=2.0,  # Start with 2 seconds for AI APIs
        max_delay=60.0,
        exponential_base=2.0,
        jitter=True,
    )
