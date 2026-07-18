import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class IssuedToken:
    match_id: str
    player_name: str


_issued_tokens: dict[str, IssuedToken] = {}


def issue_token(match_id: str, player_name: str) -> str:
    token = str(uuid.uuid4())
    _issued_tokens[token] = IssuedToken(match_id=match_id, player_name=player_name)
    return token


def validate_token(token: str, match_id: str) -> IssuedToken | None:
    issued = _issued_tokens.get(token)
    if issued is None or issued.match_id != match_id:
        return None
    return issued
