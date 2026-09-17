import pytest

from agent import graph

pytestmark = pytest.mark.anyio


@pytest.mark.langsmith
@pytest.mark.requires_ollama
async def test_agent_simple_passthrough() -> None:
    inputs = {"changeme": "some_val"}
    res = await graph.ainvoke(inputs)
    assert res is not None
