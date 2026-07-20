"""Contract + unit tests for the LLMClient seam and AgentResponse schema (architecture §4.2, §7.3).

Pins the seam's method name/signature, the async nature, its abstractness, and the AgentResponse
field shape. Any change here must update architecture.md §4.2/§7.3 in the same commit. No LLM, no
paid call — pure introspection and schema validation.
"""

import inspect

import pydantic
import pytest

from agent.llm import LLMClient
from agent.schemas import AgentResponse


def test_agent_response_shape() -> None:
    assert set(AgentResponse.model_fields) == {"move", "comment"}
    assert AgentResponse.model_fields["move"].annotation is int
    assert AgentResponse.model_fields["comment"].annotation is str


def test_agent_response_validates_well_formed() -> None:
    response = AgentResponse(move=4, comment="the center is mine")
    assert response.move == 4
    assert response.comment == "the center is mine"


def test_agent_response_rejects_malformed() -> None:
    with pytest.raises(pydantic.ValidationError):
        AgentResponse(move="not-an-int", comment="hi")  # type: ignore[arg-type]
    with pytest.raises(pydantic.ValidationError):
        AgentResponse(move=1)  # type: ignore[call-arg]  # missing comment


def test_llmclient_is_an_abstract_seam() -> None:
    assert inspect.isabstract(LLMClient)
    assert "generate_structured_response" in LLMClient.__abstractmethods__
    with pytest.raises(TypeError):
        LLMClient()  # type: ignore[abstract]


def test_generate_structured_response_signature() -> None:
    method = LLMClient.generate_structured_response
    assert inspect.iscoroutinefunction(method)  # async, per §4.2
    signature = inspect.signature(method)
    assert list(signature.parameters) == ["self", "prompt", "schema"]
    assert signature.parameters["prompt"].annotation is str
