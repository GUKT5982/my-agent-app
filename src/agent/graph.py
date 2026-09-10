"""LangGraph single-node graph template.

Sends the input to a Gemma model served through Ollama (cloud) and returns
the model's reply.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict

from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph
from langgraph.runtime import Runtime
from typing_extensions import TypedDict

# Defaults can be overridden per-request via Context, or globally via .env
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:31b-cloud")
DEFAULT_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


class Context(TypedDict, total=False):
    """Context parameters for the agent.

    Set these when creating assistants OR when invoking the graph.
    See: https://langchain-ai.github.io/langgraph/cloud/how-tos/configuration_cloud/
    """

    model: str
    base_url: str


@dataclass
class State:
    """Input/output state for the agent.

    See: https://langchain-ai.github.io/langgraph/concepts/low_level/#state
    """

    changeme: str = "example"


async def call_model(state: State, runtime: Runtime[Context]) -> Dict[str, Any]:
    """Send the input to the configured Ollama model and return its reply.

    Requires a local Ollama install that is signed in for cloud models
    (`ollama signin`) with the model pulled (`ollama pull <model>`).
    """
    context = runtime.context or {}
    llm = ChatOllama(
        model=context.get("model", DEFAULT_MODEL),
        base_url=context.get("base_url", DEFAULT_BASE_URL),
    )
    response = await llm.ainvoke(state.changeme)
    return {"changeme": response.content}


# Define the graph
graph = (
    StateGraph(State, context_schema=Context)
    .add_node(call_model)
    .add_edge("__start__", "call_model")
    .compile(name="New Graph")
)
