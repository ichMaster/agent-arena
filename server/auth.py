"""Opaque join tokens and the seat-by-token identity (architecture.md §5.2, §6.3).

The token a client receives at join **is** the ``participant_id`` — the primary key of its
``participants`` row. Identity is keyed by the token, **never** by display name (§5.2): two clients
may both be named ``"Human"`` and must not collide onto one seat. For the MVP the token is a random
opaque id; a signed/JWT form is *later* and would not change this seam. ``is_spectator`` is written
onto the participant at join, **before** any seat is assigned, so an observer can never be seated.
"""

import uuid
from dataclasses import dataclass

from server.repository import Repository


@dataclass(frozen=True)
class IssuedToken:
    """The decoded identity behind a token (§6.3)."""

    match_id: str
    player_name: str
    is_spectator: bool = False


def issue_token() -> str:
    """Return a new opaque token used as the ``participant_id`` (the ``participants`` PK)."""
    return uuid.uuid4().hex


async def validate_token(repository: Repository, match_id: str, token: str) -> IssuedToken | None:
    """Resolve ``token`` to its ``IssuedToken``, or ``None`` if unknown or from another match.

    Used at WS connect (v01.04) to reject a bad token (close ``4001``).
    """
    participant = await repository.get_participant(token)
    if participant is None or participant.match_id != match_id:
        return None
    return IssuedToken(
        match_id=participant.match_id,
        player_name=participant.player_name,
        is_spectator=participant.is_spectator,
    )
