"""
Concurrent execution utilities for agent pipeline optimization.
"""

import asyncio
from typing import List, Dict, Any, Callable, TypeVar, Optional, Tuple
from dataclasses import dataclass
from loguru import logger
import time

T = TypeVar('T')


@dataclass
class TaskResult:
    """Result wrapper for concurrent tasks."""
    name: str
    result: Any
    duration_ms: float
    error: Optional[Exception] = None


class ConcurrentExecutor:
    """Execute multiple async tasks concurrently with dependency management."""
    
    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def execute_parallel(
        self,
        tasks: List[Tuple[str, Callable]],
        timeout: Optional[float] = None
    ) -> Dict[str, TaskResult]:
        """
        Execute multiple tasks in parallel.
        
        Args:
            tasks: List of (name, coroutine_func) tuples
            timeout: Optional timeout in seconds
            
        Returns:
            Dict mapping task names to TaskResult objects
        """
        results = {}
        
        async def run_task(name: str, func: Callable) -> TaskResult:
            start_time = time.time()
            try:
                async with self.semaphore:
                    result = await func()
                    duration = (time.time() - start_time) * 1000
                    return TaskResult(name=name, result=result, duration_ms=duration)
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                logger.error(f"Task '{name}' failed: {str(e)}")
                return TaskResult(name=name, result=None, duration_ms=duration, error=e)
        
        # Create tasks
        coroutines = [run_task(name, func) for name, func in tasks]
        
        # Execute with timeout if specified
        if timeout:
            try:
                task_results = await asyncio.wait_for(
                    asyncio.gather(*coroutines, return_exceptions=True),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"Parallel execution timed out after {timeout}s")
                raise
        else:
            task_results = await asyncio.gather(*coroutines, return_exceptions=True)
        
        # Map results
        for i, (name, _) in enumerate(tasks):
            if isinstance(task_results[i], TaskResult):
                results[name] = task_results[i]
            else:
                # Handle unexpected errors
                results[name] = TaskResult(
                    name=name,
                    result=None,
                    duration_ms=0,
                    error=task_results[i] if isinstance(task_results[i], Exception) else None
                )
        
        return results
    
    async def execute_with_dependencies(
        self,
        tasks: Dict[str, Dict[str, Any]],
        timeout: Optional[float] = None
    ) -> Dict[str, TaskResult]:
        """
        Execute tasks with dependency management.
        
        Args:
            tasks: Dict of task definitions with structure:
                {
                    "task_name": {
                        "func": coroutine_function,
                        "depends_on": ["other_task_name"],
                        "args": [],
                        "kwargs": {}
                    }
                }
            timeout: Optional timeout in seconds
            
        Returns:
            Dict mapping task names to TaskResult objects
        """
        results = {}
        completed = set()
        
        async def can_run(task_name: str) -> bool:
            """Check if all dependencies are completed."""
            deps = tasks[task_name].get("depends_on", [])
            return all(dep in completed for dep in deps)
        
        async def run_task(task_name: str) -> TaskResult:
            """Run a single task with its dependencies."""
            task_def = tasks[task_name]
            func = task_def["func"]
            args = task_def.get("args", [])
            kwargs = task_def.get("kwargs", {})
            
            # Inject dependency results if needed
            if task_def.get("inject_deps", False):
                dep_results = {
                    dep: results[dep].result
                    for dep in task_def.get("depends_on", [])
                    if dep in results
                }
                kwargs["dep_results"] = dep_results
            
            start_time = time.time()
            try:
                async with self.semaphore:
                    result = await func(*args, **kwargs)
                    duration = (time.time() - start_time) * 1000
                    return TaskResult(name=task_name, result=result, duration_ms=duration)
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                logger.error(f"Task '{task_name}' failed: {str(e)}")
                return TaskResult(name=task_name, result=None, duration_ms=duration, error=e)
        
        # Execute tasks in waves based on dependencies
        remaining = set(tasks.keys())
        start_time = time.time()
        
        while remaining:
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                raise asyncio.TimeoutError(f"Execution timed out after {timeout}s")
            
            # Find tasks that can run
            ready_tasks = [
                task for task in remaining
                if await can_run(task)
            ]
            
            if not ready_tasks:
                # Circular dependency or missing dependency
                raise ValueError(f"Cannot resolve dependencies. Remaining tasks: {remaining}")
            
            # Run ready tasks in parallel
            task_coroutines = [run_task(task) for task in ready_tasks]
            wave_results = await asyncio.gather(*task_coroutines, return_exceptions=True)
            
            # Process results
            for i, task_name in enumerate(ready_tasks):
                if isinstance(wave_results[i], TaskResult):
                    results[task_name] = wave_results[i]
                    if wave_results[i].error is None:
                        completed.add(task_name)
                else:
                    results[task_name] = TaskResult(
                        name=task_name,
                        result=None,
                        duration_ms=0,
                        error=wave_results[i]
                    )
                
                remaining.remove(task_name)
        
        return results


class RequestBatcher:
    """Batch similar requests for efficient processing."""
    
    def __init__(self, batch_size: int = 10, wait_time_ms: int = 50):
        self.batch_size = batch_size
        self.wait_time_ms = wait_time_ms
        self.pending_requests = {}
        self.processing = False
    
    async def add_request(
        self,
        key: str,
        request: Any,
        processor: Callable
    ) -> Any:
        """
        Add a request to be batched.
        
        Args:
            key: Batch key for grouping similar requests
            request: The request object
            processor: Async function to process a batch of requests
            
        Returns:
            The result for this specific request
        """
        # Create future for this request
        future = asyncio.Future()
        
        # Add to pending requests
        if key not in self.pending_requests:
            self.pending_requests[key] = []
        
        self.pending_requests[key].append((request, future))
        
        # Start processing if not already running
        if not self.processing:
            asyncio.create_task(self._process_batches(processor))
        
        # Wait for result
        return await future
    
    async def _process_batches(self, processor: Callable):
        """Process pending batches."""
        self.processing = True
        
        try:
            # Wait for more requests to accumulate
            await asyncio.sleep(self.wait_time_ms / 1000)
            
            # Process each batch
            for key, requests in list(self.pending_requests.items()):
                if not requests:
                    continue
                
                # Take up to batch_size requests
                batch = requests[:self.batch_size]
                self.pending_requests[key] = requests[self.batch_size:]
                
                # Extract request objects
                batch_requests = [req for req, _ in batch]
                
                try:
                    # Process batch
                    results = await processor(batch_requests)
                    
                    # Distribute results
                    for i, (_, future) in enumerate(batch):
                        if i < len(results):
                            future.set_result(results[i])
                        else:
                            future.set_exception(
                                Exception("Batch processor returned fewer results than requests")
                            )
                
                except Exception as e:
                    # Set exception for all requests in batch
                    for _, future in batch:
                        future.set_exception(e)
                
                # Clean up empty batches
                if not self.pending_requests[key]:
                    del self.pending_requests[key]
        
        finally:
            self.processing = False


_executor: Optional[ConcurrentExecutor] = None
_batcher: Optional[RequestBatcher] = None


def get_executor() -> ConcurrentExecutor:
    """Get global concurrent executor instance."""
    global _executor
    if _executor is None:
        _executor = ConcurrentExecutor(max_concurrent=10)
    return _executor


def get_batcher() -> RequestBatcher:
    """Get global request batcher instance."""
    global _batcher
    if _batcher is None:
        _batcher = RequestBatcher(batch_size=10, wait_time_ms=50)
    return _batcher
