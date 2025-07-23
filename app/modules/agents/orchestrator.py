"""
Agent Orchestrator - Unopinionated orchestration engine for agent pipelines.
Provides execution means without defining the pipeline structure.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional, TypeVar

from loguru import logger

if TYPE_CHECKING:
    from app.modules.agents.registry import AgentRegistry

T = TypeVar("T")


class ExecutionStrategy(str, Enum):
    """Execution strategies for pipeline steps."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


@dataclass
class PipelineStep:
    """Represents a single step in the pipeline."""

    name: str
    func: Callable[..., Any]
    strategy: ExecutionStrategy = ExecutionStrategy.SEQUENTIAL
    dependencies: list[str] | None = None
    condition: Callable[[dict[str, Any]], bool] | None = None

    def __post_init__(self) -> None:
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class StepResult:
    """Result from a pipeline step execution."""

    name: str
    result: Any
    duration_ms: float
    success: bool = True
    error: str | None = None


class AgentOrchestrator:
    """
    Unopinionated orchestrator that provides execution capabilities.
    The actual pipeline structure is defined externally.
    """

    def __init__(self, registry: Optional["AgentRegistry"] = None):
        self._execution_history: list[StepResult] = []
        self._registry = registry

    async def execute_pipeline(
        self, steps: list[PipelineStep], context: dict[str, Any], timeout: float | None = None
    ) -> dict[str, StepResult]:
        """
        Execute a pipeline of steps with the given context.

        Args:
            steps: List of pipeline steps to execute
            context: Initial context passed to steps
            timeout: Optional timeout for the entire pipeline

        Returns:
            Dictionary mapping step names to their results
        """
        results: dict[str, StepResult] = {}

        try:
            if timeout:
                return await asyncio.wait_for(self._execute_steps(steps, context, results), timeout=timeout)
            else:
                return await self._execute_steps(steps, context, results)
        except TimeoutError:
            logger.error(f"Pipeline execution timed out after {timeout}s")
            raise
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e!s}")
            raise

    async def _execute_steps(
        self, steps: list[PipelineStep], context: dict[str, Any], results: dict[str, StepResult]
    ) -> dict[str, StepResult]:
        """Execute steps based on their strategies and dependencies."""
        # Group steps by execution order based on dependencies
        execution_groups = self._group_steps_by_dependencies(steps)

        for group in execution_groups:
            # Execute steps in the group based on their strategies
            group_results = await self._execute_group(group, context, results)
            results.update(group_results)

        return results

    async def _execute_group(
        self, steps: list[PipelineStep], context: dict[str, Any], previous_results: dict[str, StepResult]
    ) -> dict[str, StepResult]:
        """Execute a group of steps that can run together."""
        # Separate parallel and sequential steps
        parallel_steps = [s for s in steps if s.strategy == ExecutionStrategy.PARALLEL]
        sequential_steps = [s for s in steps if s.strategy == ExecutionStrategy.SEQUENTIAL]
        conditional_steps = [s for s in steps if s.strategy == ExecutionStrategy.CONDITIONAL]

        logger.debug(
            f"Executing group with {len(parallel_steps)} parallel, "
            f"{len(sequential_steps)} sequential, {len(conditional_steps)} conditional steps"
        )

        results = {}

        # Execute parallel steps concurrently
        if parallel_steps:
            parallel_results = await self._execute_parallel(parallel_steps, context, previous_results)
            results.update(parallel_results)
            # Update previous_results for dependency tracking
            previous_results.update(parallel_results)

        # Execute sequential steps one by one
        for step in sequential_steps:
            step_result = await self._execute_step(step, context, previous_results)
            results[step.name] = step_result
            previous_results[step.name] = step_result

        # Execute conditional steps if their conditions are met
        for step in conditional_steps:
            if step.condition and step.condition(previous_results):
                step_result = await self._execute_step(step, context, previous_results)
                results[step.name] = step_result
                previous_results[step.name] = step_result

        return results

    async def _execute_parallel(
        self, steps: list[PipelineStep], context: dict[str, Any], previous_results: dict[str, StepResult]
    ) -> dict[str, StepResult]:
        """Execute multiple steps in parallel."""
        logger.debug(f"Executing {len(steps)} steps in parallel: {[s.name for s in steps]}")

        # Create all tasks first
        tasks = []
        for step in steps:
            task = asyncio.create_task(self._execute_step(step, context, previous_results))
            tasks.append((step.name, task))

        # Wait for all tasks to complete using gather
        task_list = [task for _, task in tasks]
        completed_tasks = await asyncio.gather(*task_list, return_exceptions=True)

        # Process results
        results = {}
        for i, (name, _) in enumerate(tasks):
            task_result = completed_tasks[i]
            if isinstance(task_result, StepResult):
                results[name] = task_result
            elif isinstance(task_result, Exception):
                logger.error(f"Parallel step {name} failed: {task_result!s}")
                results[name] = StepResult(name=name, result=None, duration_ms=0, success=False, error=str(task_result))
            else:
                # This shouldn't happen, but handle it gracefully
                logger.error(f"Unexpected result type for step {name}: {type(task_result)}")
                results[name] = StepResult(name=name, result=task_result, duration_ms=0, success=True)

        return results

    async def _execute_step(
        self, step: PipelineStep, context: dict[str, Any], previous_results: dict[str, StepResult]
    ) -> StepResult:
        """Execute a single step."""
        start_time = time.time()

        try:
            # Prepare arguments for the step function
            if self._requires_context(step.func):
                if self._requires_results(step.func):
                    result = await step.func(context, previous_results)
                else:
                    result = await step.func(context)
            else:
                result = await step.func()

            duration_ms = (time.time() - start_time) * 1000

            step_result = StepResult(name=step.name, result=result, duration_ms=duration_ms, success=True)

            logger.debug(f"Step {step.name} completed in {duration_ms:.2f}ms")
            return step_result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Step {step.name} failed: {e!s}")

            return StepResult(name=step.name, result=None, duration_ms=duration_ms, success=False, error=str(e))

    def _group_steps_by_dependencies(self, steps: list[PipelineStep]) -> list[list[PipelineStep]]:
        """Group steps by their dependencies for execution order."""
        # Simple implementation - could be enhanced with topological sort
        groups = []
        executed: set[str] = set()
        remaining = steps.copy()

        while remaining:
            # Find steps that can be executed (all dependencies met)
            ready = [step for step in remaining if all(dep in executed for dep in (step.dependencies or []))]

            if not ready:
                # Circular dependency or missing dependency
                raise ValueError(f"Cannot resolve dependencies. Remaining steps: {[s.name for s in remaining]}")

            groups.append(ready)
            executed.update(s.name for s in ready)
            remaining = [s for s in remaining if s not in ready]

        return groups

    def _requires_context(self, func: Callable[..., Any]) -> bool:
        """Check if function requires context parameter."""
        import inspect

        sig = inspect.signature(func)
        return len(sig.parameters) >= 1

    def _requires_results(self, func: Callable[..., Any]) -> bool:
        """Check if function requires previous results parameter."""
        import inspect

        sig = inspect.signature(func)
        return len(sig.parameters) >= 2

    def get_execution_history(self) -> list[StepResult]:
        """Get the execution history of pipeline steps."""
        return self._execution_history.copy()

    def clear_history(self) -> None:
        """Clear execution history."""
        self._execution_history.clear()


# Utility functions for building pipelines
def sequential(*funcs: Callable[..., Any]) -> list[PipelineStep]:
    """Create sequential pipeline steps from functions."""
    return [PipelineStep(name=func.__name__, func=func, strategy=ExecutionStrategy.SEQUENTIAL) for func in funcs]


def parallel(*funcs: Callable[..., Any]) -> list[PipelineStep]:
    """Create parallel pipeline steps from functions."""
    return [PipelineStep(name=func.__name__, func=func, strategy=ExecutionStrategy.PARALLEL) for func in funcs]


def step(
    name: str,
    func: Callable[..., Any],
    strategy: ExecutionStrategy = ExecutionStrategy.SEQUENTIAL,
    dependencies: list[str] | None = None,
    condition: Callable[[dict[str, Any]], bool] | None = None,
) -> PipelineStep:
    """Create a custom pipeline step."""
    return PipelineStep(name=name, func=func, strategy=strategy, dependencies=dependencies or [], condition=condition)
