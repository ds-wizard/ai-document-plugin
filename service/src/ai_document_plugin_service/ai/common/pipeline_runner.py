from __future__ import annotations

from typing import TYPE_CHECKING, Any

from haystack.core.errors import PipelineRuntimeError

if TYPE_CHECKING:
    from haystack import AsyncPipeline


async def run_haystack_pipeline(
    pipeline: AsyncPipeline,
    data: dict[str, Any],
    include_outputs_from: set[str] | None = None,
) -> dict[str, Any]:
    # Haystack wraps component failures in PipelineRuntimeError; re-raise the component's own exception.
    try:
        return await pipeline.run_async(data=data, include_outputs_from=include_outputs_from)
    except PipelineRuntimeError as error:
        cause = error.__cause__
        if not isinstance(cause, Exception):
            raise
        raise cause from None
