"""The fixed 404 answers of the token routes: one body for every kind of miss.

An unknown, expired, used, rotated or revoked token must be indistinguishable, so these
answers carry no trace id in the body and no detail that depends on the cause. The trace id
stays in the `X-Trace-Id` header that the middleware adds.
"""

from __future__ import annotations

from fastapi import Response

from app.shared.errors import PROBLEM_CONTENT_TYPE, ProblemDetail


class InvalidTokenError(Exception):
    """The token is unknown, expired, used, rotated or revoked."""


def _fixed(code: str, detail: str) -> Response:
    problem = ProblemDetail(
        type=f"app://error/{code}", title="Not Found", status=404, code=code, detail=detail
    )
    return Response(
        problem.model_dump_json(exclude_none=True),
        status_code=404,
        media_type=PROBLEM_CONTENT_TYPE,
        headers={"Cache-Control": "no-store"},
    )


def invalid_token_response() -> Response:
    """Return the 404 of a confirmation or management token."""
    return _fixed("invalid_token", "Dieser Link ist ungültig oder abgelaufen.")


def calendar_not_found_response() -> Response:
    """Return the 404 of a profile calendar (same for unknown, rotated and revoked)."""
    return _fixed("not_found", "calendar not found")
