"""Auth token — the opaque join token that *is* the participant_id (architecture.md §5.2, §6.3).

Identity is keyed by this token, never by display name: two browser sessions both named "Human" get
distinct tokens and therefore distinct seats. `issue_token` mints the opaque id (also the
`participants` PK); `validate_token` resolves a token+match to an `IssuedToken` via the Repository.
For the MVP the token is a random opaque string; a signed/JWT form is later and would not change this
seam. The token never leaves the server except back to the client that owns it.
"""

import secrets
from dataclasses import dataclass

from server.repository import Repository


@dataclass(frozen=True)
class IssuedToken:
    """The seat-bearing identity resolved from a token (§6.3)."""

    match_id: str
    player_name: str
    is_spectator: bool = False


def issue_token() -> str:
    """A unique opaque id, used as the participant PK (§5.2)."""
    return secrets.token_urlsafe(32)


async def validate_token(repo: Repository, match_id: str, token: str) -> IssuedToken | None:
    """Resolve a token to its IssuedToken, or None if unknown or from a different match."""
    participant = await repo.get_participant(token)
    if participant is None or participant.match_id != match_id:
        return None
    return IssuedToken(
        match_id=participant.match_id,
        player_name=participant.player_name,
        is_spectator=participant.is_spectator,
    )
