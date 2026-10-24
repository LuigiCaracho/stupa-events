"""ALTCHA challenge endpoint: `GET /api/public/altcha/challenge`.

Issues a fresh HMAC-signed proof-of-work challenge. The browser solves it with Web Crypto
and sends the solution in the body of the public POST; the API verifies it locally
(`shared.antiabuse.verify_altcha_solution`). Without `ALTCHA_HMAC_SECRET` the route is 404.
It sets no cookie and is never cached.

Copied from STUPA-Workflow@93c33d6 backend/app/modules/antiabuse/router.py (public path, no-store)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response

from app.modules.auth.schemas import CamelModel
from app.shared.altcha import create_challenge
from app.shared.antiabuse import SettingsDep, now_unix
from app.shared.errors import NotFoundError, ProblemDetail

router = APIRouter(prefix="/public/altcha", tags=["public"])
_PROBLEM: dict[str, Any] = {"model": ProblemDetail}


class AltchaChallengeOut(CamelModel):
    """ALTCHA proof-of-work challenge in the altcha-lib format."""

    algorithm: str
    challenge: str
    salt: str
    signature: str
    maxnumber: int


@router.get("/challenge", response_model=AltchaChallengeOut, responses={404: _PROBLEM})
def altcha_challenge(settings: SettingsDep, response: Response) -> AltchaChallengeOut:
    """Issue a fresh proof-of-work challenge (404 while ALTCHA is not configured)."""
    if not settings.altcha_enabled:
        raise NotFoundError("Altcha is not configured.")
    assert settings.altcha_hmac_secret is not None
    challenge = create_challenge(
        settings.altcha_hmac_secret,
        expires=now_unix() + settings.altcha_challenge_ttl_seconds,
        max_number=settings.altcha_max_number,
    )
    response.headers["Cache-Control"] = "no-store"
    return AltchaChallengeOut(
        algorithm=challenge.algorithm,
        challenge=challenge.challenge,
        salt=challenge.salt,
        signature=challenge.signature,
        maxnumber=challenge.maxnumber,
    )
