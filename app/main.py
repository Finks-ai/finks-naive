import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from loguru import logger
import asyncio

from app.core.config import get_settings
from app.core.database import get_db_service

# Check if we're in Lambda environment
IS_LAMBDA = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI.
    Handles initialization and cleanup with Lambda optimizations when applicable.
    """
    logger.info(f"Starting up Finks Naive API{' (Lambda)' if IS_LAMBDA else ''}...")
    
    if IS_LAMBDA:
        # Import Lambda optimizer only if in Lambda environment
        from app.core.optimizer import LambdaOptimizer, get_connection_pool_manager
        
        # Apply Lambda optimizations
        LambdaOptimizer.optimize_for_lambda()
        
        # Initialize connection pool manager
        pool_manager = get_connection_pool_manager()
        
        # Warm up connections
        LambdaOptimizer.warmup_connections()
        
        # Run async warmup tasks
        await LambdaOptimizer.run_warmup_tasks()
    else:
        # Standard initialization for non-Lambda environments
        db_service = get_db_service()
        try:
            db_service.get_client()
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    logger.info("Startup complete")
    
    yield
    
    # Cleanup on shutdown
    if IS_LAMBDA:
        # Minimal cleanup for Lambda (connections persist across invocations)
        logger.info("Lambda environment - minimal cleanup")
    else:
        # Full cleanup for non-Lambda environments
        try:
            db_service = get_db_service()
            db_service.close()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

app = FastAPI(
    title="Finks Naive API",
    description="Natural language to MongoDB query converter using multi-agent AI",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from app.modules.agents.router import router as agents_router
from app.modules.settings.router import router as settings_router

app.include_router(agents_router)
app.include_router(settings_router)

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": f"Finks Naive API - Environment: {settings.ENVIRONMENT}",
        "version": "0.2.0",
        "docs_url": "/docs",
        "lambda_environment": IS_LAMBDA,
        "optimizations": {
            "parallel_execution": True,
            "multi_level_caching": True,
            "connection_pooling": True,
            "lambda_optimized": IS_LAMBDA
        } if IS_LAMBDA else {}
    }

# Health check endpoint
@app.get("/health")
async def health():
    try:
        if IS_LAMBDA:
            # Use connection pool manager in Lambda
            from app.core.optimizer import get_connection_pool_manager
            pool_manager = get_connection_pool_manager()
            db = pool_manager.get_database(settings.MONGODB_DB_NAME)
            db.command('ping')
            
            # Get cache stats if available
            try:
                from app.core.cache import get_query_cache
                cache = get_query_cache()
                cache_stats = cache.get_stats()
            except ImportError:
                cache_stats = None
            
            return {
                "status": "healthy",
                "database": "connected",
                "cache_stats": cache_stats,
                "lambda_environment": True
            }
        else:
            # Standard health check
            db_service = get_db_service()
            db_service.get_client().admin.command('ping')
            return {
                "status": "healthy",
                "database": "connected",
                "lambda_environment": False
            }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Health check failed: {e}")

# Performance stats endpoint (only if optimizations are available)
@app.get("/stats/performance")
async def performance_stats():
    """Get performance statistics including cache hit rates and execution times."""
    try:
        from app.core.cache import get_query_cache
        cache = get_query_cache()
        
        return {
            "cache_performance": cache.get_stats(),
            "lambda_optimized": IS_LAMBDA,
            "optimizations_enabled": {
                "parallel_execution": True,
                "multi_level_caching": True,
                "connection_pooling": True,
                "lazy_loading": IS_LAMBDA,
                "request_batching": True
            }
        }
    except ImportError:
        # Return basic stats if optimization modules not available
        return {
            "lambda_optimized": IS_LAMBDA,
            "optimizations_enabled": {
                "parallel_execution": False,
                "multi_level_caching": False,
                "connection_pooling": False,
                "lazy_loading": False,
                "request_batching": False
            }
        }

# Configure Mangum handler based on environment
if IS_LAMBDA:
    # Lambda deployment with lifespan="off" for MongoDB compatibility
    # Also wrap handler if lambda optimization available
    raw_handler = Mangum(app, lifespan="off")
    
    try:
        from app.core.optimizer import lambda_handler_wrapper
        handler = lambda_handler_wrapper(raw_handler)
    except ImportError:
        # Use raw handler if wrapper not available
        handler = raw_handler
else:
    # Standard handler for non-Lambda environments
    handler = Mangum(app, lifespan="auto")

# Register warmup tasks for Lambda (if available)
if IS_LAMBDA:
    try:
        from app.core.optimizer import LambdaOptimizer
        
        def register_warmup_tasks():
            """Register tasks to run during Lambda warmup."""
            
            async def warmup_agents():
                """Preload agent models."""
                try:
                    # Try optimized service first
                    from app.modules.agents.service_optimized import optimized_agent_pipeline_service
                    service = optimized_agent_pipeline_service
                except ImportError:
                    # Fall back to standard service
                    from app.modules.agents.service import agent_pipeline_service
                    service = agent_pipeline_service
                
                # Just accessing properties will trigger lazy loading
                _ = service.field_extraction
                _ = service.sorting_extraction
                logger.info("Agent models warmed up")
            
            async def warmup_cache():
                """Initialize cache connections."""
                try:
                    from app.core.cache import get_query_cache
                    cache = get_query_cache()
                    # Test cache operations
                    test_key = "_warmup_test"
                    await cache.set_cached_result(test_key, {"test": True}, ttl_seconds=60)
                    await cache.get_cached_result(test_key)
                    logger.info("Cache warmed up")
                except ImportError:
                    logger.info("Cache module not available for warmup")
            
            LambdaOptimizer.register_warmup_task(warmup_agents)
            LambdaOptimizer.register_warmup_task(warmup_cache)
        
        # Register warmup tasks
        register_warmup_tasks()
    except ImportError:
        logger.info("Lambda optimization module not available")

# For local development
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)