"""
Lambda optimization utilities for cold start reduction and connection pooling.
"""

import asyncio
import os
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, ClassVar

from loguru import logger
from pymongo import MongoClient


class LambdaOptimizer:
    """Utilities for optimizing Lambda execution."""

    # Shared connection pool for Lambda container reuse
    _mongo_client: ClassVar[MongoClient[dict[str, Any]] | None] = None
    _initialization_complete: ClassVar[bool] = False
    _warmup_tasks: ClassVar[list[Callable[[], Awaitable[None]]]] = []

    @classmethod
    def get_mongo_client(cls) -> MongoClient[dict[str, Any]]:
        """Get or create MongoDB client with connection pooling optimized for Lambda."""
        if cls._mongo_client is None:
            from app.core.config import get_settings

            settings = get_settings()

            # Optimized connection settings for Lambda
            cls._mongo_client = MongoClient(
                settings.MONGODB_URL,
                # Connection pool settings
                maxPoolSize=1,  # Lambda containers are single-threaded
                minPoolSize=0,  # Don't maintain idle connections
                maxIdleTimeMS=45000,  # Close idle connections after 45s
                waitQueueTimeoutMS=2500,  # Fail fast if no connection available
                serverSelectionTimeoutMS=5000,  # Fail fast on server selection
                connectTimeoutMS=2000,  # Fast connection timeout
                socketTimeoutMS=5000,  # Socket operation timeout
                # Retry settings
                retryWrites=True,
                retryReads=True,
                # Other optimizations
                connect=False,  # Lazy connection
                directConnection=False,
                appname="finks-lambda",
            )

            logger.info("MongoDB client initialized with Lambda optimizations")

        return cls._mongo_client

    @classmethod
    def is_lambda_environment(cls) -> bool:
        """Check if running in Lambda environment."""
        return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

    @classmethod
    def warmup_connections(cls) -> None:
        """Warm up database connections during container init."""
        if cls._initialization_complete:
            return

        try:
            client = cls.get_mongo_client()
            # Ping to establish connection
            client.admin.command("ping")
            logger.info("MongoDB connection warmed up")

            cls._initialization_complete = True
        except Exception as e:
            logger.warning(f"Connection warmup failed: {e}")

    @classmethod
    def register_warmup_task(cls, task_func: Callable[[], Awaitable[None]]) -> None:
        """Register an async task to run during warmup."""
        cls._warmup_tasks.append(task_func)

    @classmethod
    async def run_warmup_tasks(cls) -> None:
        """Run all registered warmup tasks."""
        if not cls._warmup_tasks:
            return

        logger.info(f"Running {len(cls._warmup_tasks)} warmup tasks")

        # Run warmup tasks concurrently
        results = await asyncio.gather(*[task() for task in cls._warmup_tasks], return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Warmup task {i} failed: {result}")

        logger.info("Warmup tasks completed")

    @classmethod
    def optimize_for_lambda(cls) -> None:
        """Apply Lambda-specific optimizations."""
        if not cls.is_lambda_environment():
            return

        # Reduce thread pool sizes
        import concurrent.futures

        concurrent.futures.ThreadPoolExecutor._max_workers = 2

        # Optimize asyncio for Lambda
        loop = asyncio.get_event_loop()
        loop.set_debug(False)

        # Disable unnecessary logging in production
        if os.environ.get("ENVIRONMENT") == "production":
            import logging

            logging.getLogger("boto3").setLevel(logging.WARNING)
            logging.getLogger("botocore").setLevel(logging.WARNING)
            logging.getLogger("urllib3").setLevel(logging.WARNING)

        logger.info("Lambda optimizations applied")


def lambda_handler_wrapper(
    handler_func: Callable[[dict[str, Any], Any], dict[str, Any]],
) -> Callable[[dict[str, Any], Any], dict[str, Any]]:
    """Decorator to wrap Lambda handlers with optimizations."""

    @wraps(handler_func)
    def wrapper(event: dict[str, Any], context: Any) -> dict[str, Any]:
        # Apply optimizations
        LambdaOptimizer.optimize_for_lambda()

        # Warm up connections
        LambdaOptimizer.warmup_connections()

        # Run the actual handler
        return handler_func(event, context)

    return wrapper


# Connection pool manager for better connection reuse
class ConnectionPoolManager:
    """Manage database connections with pooling optimized for Lambda."""

    def __init__(self) -> None:
        self._db_cache: dict[str, Any] = {}

    def get_database(self, db_name: str) -> Any:
        """Get database with connection caching."""
        if db_name not in self._db_cache:
            client = LambdaOptimizer.get_mongo_client()
            self._db_cache[db_name] = client[db_name]
        return self._db_cache[db_name]

    def get_collection(self, db_name: str, collection_name: str) -> Any:
        """Get collection with connection caching."""
        db = self.get_database(db_name)
        return db[collection_name]

    def close_all(self) -> None:
        """Close all connections (for cleanup)."""
        self._db_cache.clear()
        if LambdaOptimizer._mongo_client:
            LambdaOptimizer._mongo_client.close()
            LambdaOptimizer._mongo_client = None


# Global connection pool manager
_connection_pool_manager: ConnectionPoolManager | None = None


def get_connection_pool_manager() -> ConnectionPoolManager:
    """Get global connection pool manager."""
    global _connection_pool_manager
    if _connection_pool_manager is None:
        _connection_pool_manager = ConnectionPoolManager()
    return _connection_pool_manager


# Preload frequently used modules during container init
def preload_modules() -> None:
    """Preload heavy modules to reduce cold start time."""
    import_modules = ["pydantic_ai", "numpy", "pandas", "pymongo", "fastapi", "mangum"]

    for module_name in import_modules:
        try:
            __import__(module_name)
            logger.debug(f"Preloaded {module_name}")
        except ImportError:
            pass


# Run preloading when module is imported (container init)
if LambdaOptimizer.is_lambda_environment():
    preload_modules()
