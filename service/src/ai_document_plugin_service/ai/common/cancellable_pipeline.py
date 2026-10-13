"""Cancellation adapter for Haystack's component runners, not arbitrary asyncio tasks."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, cast

from haystack import AsyncPipeline, tracing
from haystack.dataclasses.breakpoints import Breakpoint

from ai_document_plugin_service.ai.common.async_tasks import cancel_and_wait


@dataclass
class _ComponentRun:
    owner: asyncio.Task | None
    tasks: set[asyncio.Task] = field(default_factory=set)
    closing: bool = False


# Inherited by Haystack runners, including ones waiting for its concurrency slot.
# Registration is explicit at the component boundary; library cleanup tasks are excluded.
_COMPONENT_RUN: ContextVar[_ComponentRun] = ContextVar('component_run')


class CancellableAsyncPipeline(AsyncPipeline):
    """Own the component runners Haystack otherwise leaves running on cancellation.

    The private component hook is the only Haystack-specific integration point.
    Keep its compatibility covered by real-pipeline tests when updating Haystack.
    """

    async def run_async_generator(
        self, data: dict[str, Any], include_outputs_from: set[str] | None = None, concurrency_limit: int = 4
    ) -> AsyncIterator[dict[str, Any]]:
        run = _ComponentRun(owner=asyncio.current_task())
        token = _COMPONENT_RUN.set(run)
        # Haystack annotates this as AsyncIterator but implements an async generator.
        results = cast(
            'AsyncGenerator[dict[str, Any]]',
            super().run_async_generator(data, include_outputs_from, concurrency_limit),
        )
        try:
            async for result in results:
                yield result
        finally:
            # Block queued components before releasing any active runner's semaphore.
            run.closing = True
            try:
                await cancel_and_wait(run.tasks)
            finally:
                try:
                    await results.aclose()
                finally:
                    _COMPONENT_RUN.reset(token)

    @staticmethod
    async def _run_component_async(
        component_name: str,
        component: dict[str, Any],
        component_inputs: dict[str, Any],
        component_visits: dict[str, int],
        parent_span: tracing.Span | None = None,
        *,
        break_point: Breakpoint | None = None,
    ) -> Mapping[str, Any]:
        run = _COMPONENT_RUN.get()
        if run.closing:
            raise asyncio.CancelledError
        task = asyncio.current_task()
        # Haystack can run an isolated component directly on the orchestration task.
        # That task is already unwinding when the outer finally runs; never cancel itself.
        if task is not None and task is not run.owner:
            run.tasks.add(task)
        return await AsyncPipeline._run_component_async(  # ruff: ignore[private-member-access] - isolated Haystack adapter
            component_name, component, component_inputs, component_visits, parent_span, break_point=break_point
        )
