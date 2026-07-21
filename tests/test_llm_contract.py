"""Contract test pinning the LLMClient seam + AgentResponse schema (architecture.md §4.2/§7.3).

If this changes, the seam changed — update architecture §4.2 in the same commit. No LLM, no paid call.
"""

import inspect
from typing import get_type_hints

import pydantic
import pytest

from agent.llm import LLMClient
from agent.schemas import AgentResponse


def test_llm_client_is_abstract() -> None:
    assert inspect.isabstract(LLMClient)
    with pytest.raises(TypeError):
        LLMClient()  # type: ignore[abstract]


def test_generate_structured_response_signature() -> None:
    method = LLMClient.generate_structured_response
    assert inspect.iscoroutinefunction(method)
    sig = inspect.signature(method)
    assert list(sig.parameters) == ["self", "prompt", "schema"]
    assert sig.parameters["prompt"].annotation is str


def test_llm_imports_nothing_from_server() -> None:
    import agent.llm

    src = inspect.getsource(agent.llm)
    assert "import server" not in src
    assert "from server" not in src


def test_agent_response_shape() -> None:
    hints = get_type_hints(AgentResponse)
    assert hints["move"] is int
    assert hints["comment"] is str


def test_agent_response_validates_and_rejects() -> None:
    ok = AgentResponse(move=4, comment="mine")
    assert ok.move == 4 and ok.comment == "mine"
    with pytest.raises(pydantic.ValidationError):
        AgentResponse(move="not-an-int", comment="x")  # type: ignore[arg-type]
    with pytest.raises(pydantic.ValidationError):
        AgentResponse(comment="missing move")  # type: ignore[call-arg]
