from typing import Any

import pytest
from haystack import AsyncPipeline, component
from haystack.core.component import Component

from ai_document_plugin_service.ai.common.pipeline_runner import run_haystack_pipeline


class _ComponentError(Exception):
    pass


@component
class _Echo:
    @component.output_types(value=str)
    async def run_async(self, value: str) -> dict[str, Any]:  # ruff: ignore[no-self-use]
        return {'value': value}

    @component.output_types(value=str)
    def run(self, value: str) -> dict[str, Any]:
        raise NotImplementedError


@component
class _Failing:
    @component.output_types(value=str)
    async def run_async(self, value: str) -> dict[str, Any]:  # ruff: ignore[no-self-use]
        raise _ComponentError(value)

    @component.output_types(value=str)
    def run(self, value: str) -> dict[str, Any]:
        raise NotImplementedError


def _pipeline(instance: Component) -> AsyncPipeline:
    pipeline = AsyncPipeline()
    pipeline.add_component('step', instance)
    return pipeline


async def test_returns_pipeline_result() -> None:
    result = await run_haystack_pipeline(_pipeline(_Echo()), data={'step': {'value': 'ok'}})

    assert result == {'step': {'value': 'ok'}}


async def test_unwraps_component_exception() -> None:
    with pytest.raises(_ComponentError, match='boom'):
        await run_haystack_pipeline(_pipeline(_Failing()), data={'step': {'value': 'boom'}})
