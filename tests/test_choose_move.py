"""choose_move tests (ARENA-OPUS-OPUS-023). LLMClient mocked -- no paid call."""

from unittest.mock import AsyncMock

from agent.agent import choose_move
from agent.memory import MemoryWindow
from agent.schemas import AgentResponse

BOARD = [""] * 9
VALID = [0, 1, 2, 5, 8]
PERSONA = "You are Ironclaw."


def _llm(*replies: object) -> AsyncMock:
    llm = AsyncMock()
    llm.generate_structured_response = AsyncMock(side_effect=list(replies))
    return llm


async def test_legal_first_try() -> None:
    llm = _llm(AgentResponse(move=5, comment="boom"))
    move, comment = await choose_move(llm, MemoryWindow(5), BOARD, VALID, PERSONA)
    assert move == 5 and comment == "boom"
    assert llm.generate_structured_response.await_count == 1


async def test_illegal_then_legal_retries() -> None:
    llm = _llm(AgentResponse(move=99, comment="oops"), AgentResponse(move=2, comment="better"))
    move, _ = await choose_move(llm, MemoryWindow(5), BOARD, VALID, PERSONA)
    assert move == 2
    assert llm.generate_structured_response.await_count == 2


async def test_all_illegal_falls_back_to_legal() -> None:
    llm = _llm(*[AgentResponse(move=99, comment="no") for _ in range(3)])
    move, _ = await choose_move(llm, MemoryWindow(5), BOARD, VALID, PERSONA)
    assert move in VALID  # a random legal move, never stalls
    assert llm.generate_structured_response.await_count == 3


async def test_model_error_falls_back_to_legal() -> None:
    llm = AsyncMock()
    llm.generate_structured_response = AsyncMock(side_effect=RuntimeError("model down"))
    move, _ = await choose_move(llm, MemoryWindow(5), BOARD, VALID, PERSONA)
    assert move in VALID
    assert llm.generate_structured_response.await_count == 3  # exhausted attempts, then fallback
