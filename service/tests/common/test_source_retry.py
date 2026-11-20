import pytest


async def test_retry_repairs_invalid_id_and_reports_valid_choices() -> None:
    from unittest.mock import AsyncMock

    from ai_document_plugin_service.ai.common.source_retry import generate_with_valid_sources

    generate = AsyncMock(
        side_effect=[
            '<statement source="q0">Text.</statement>',
            '<statement source="q1">Text.</statement>',
        ]
    )
    result = await generate_with_valid_sources(generate, {'q1'}, require_sources=True)
    assert result == '<statement source="q1">Text.</statement>'
    assert generate.await_count == 2
    assert generate.await_args_list[0].args == ('',)
    feedback = generate.await_args_list[1].args[0]
    assert 'Unknown statement source IDs: q0' in feedback
    assert 'Allowed source IDs: q1.' in feedback
    assert '<statement source="q0">Text.</statement>' in feedback


async def test_retry_is_bounded_and_rejects_removal_of_all_annotations() -> None:
    from unittest.mock import AsyncMock

    from ai_document_plugin_service.ai.common.source_ids import SourceValidationError
    from ai_document_plugin_service.ai.common.source_retry import generate_with_valid_sources

    generate = AsyncMock(return_value='Text without annotations.')
    with pytest.raises(SourceValidationError, match='removed'):
        await generate_with_valid_sources(generate, {'q1'}, require_sources=True)
    assert generate.await_count == 3


async def test_unrelated_errors_are_not_retried() -> None:
    from unittest.mock import AsyncMock

    from ai_document_plugin_service.ai.common.source_retry import generate_with_valid_sources

    generate = AsyncMock(side_effect=RuntimeError('Connection failed'))
    with pytest.raises(RuntimeError, match='Connection failed'):
        await generate_with_valid_sources(generate, {'q1'})
    assert generate.await_count == 1


async def test_polishing_retry_keeps_original_input_and_counts_all_calls() -> None:
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from ai_document_plugin_service.ai.common.config import load_config
    from ai_document_plugin_service.ai.polishing.dmp_polisher_component import DmpPolisherComponent
    from ai_document_plugin_service.ai.polishing.llm import SectionPolishingLLM

    original = '<statement source="q1">Data are archived.</statement>'
    invalid = '<statement source="q0">Data are archived.</statement>'
    client = Mock()
    client.completion = AsyncMock(
        side_effect=[
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            )
            for content in (invalid, original)
        ]
    )
    config = load_config(str(Path(__file__).resolve().parents[2] / 'config.test.yaml'))
    component = DmpPolisherComponent(SectionPolishingLLM(client, config, 'en'))
    result = await component.run_async(markdown=original)
    assert result['markdown'] == original
    assert result['stats'].total_calls == 2
    first, repaired = [call.kwargs['messages'] for call in client.completion.await_args_list]
    assert repaired[:2] == first
    assert original in repaired[1]['content']
    assert invalid in repaired[2]['content']
    assert 'Allowed source IDs: q1.' in repaired[2]['content']


@pytest.mark.parametrize('succeeds', [True, False])
async def test_generation_llm_validates_section_ids_and_retries(succeeds: bool) -> None:
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from ai_document_plugin_service.ai.common.config import load_config
    from ai_document_plugin_service.ai.common.source_ids import SourceValidationError
    from ai_document_plugin_service.ai.common.types import AssignmentStats
    from ai_document_plugin_service.ai.generation.llm import SectionGenerationLLM

    invalid = '<statement source="q2">Text.</statement>'
    valid = '<statement source="q1">Text.</statement>'
    responses = [invalid, valid] if succeeds else [invalid] * 3
    client = Mock()
    client.completion = AsyncMock(
        side_effect=[
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            )
            for content in responses
        ]
    )
    config = load_config(str(Path(__file__).resolve().parents[2] / 'config.test.yaml'))
    llm = SectionGenerationLLM(client, config, 'en')
    stats = AssignmentStats()
    prompt = 'Question: Storage\nSource ID: q1\nAnswer: Archive'
    if succeeds:
        assert await llm.section_from_qa(prompt, stats, allowed_source_ids={'q1'}) == valid
    else:
        with pytest.raises(SourceValidationError, match='q2'):
            await llm.section_from_qa(prompt, stats, allowed_source_ids={'q1'})
    assert client.completion.await_count == len(responses)
    assert stats.total_calls == len(responses)
    first, repaired = [call.kwargs['messages'] for call in client.completion.await_args_list[:2]]
    assert first[1]['content'] == prompt
    assert repaired[:2] == first
    assert 'Allowed source IDs: q1.' in repaired[2]['content']
    assert invalid in repaired[2]['content']
