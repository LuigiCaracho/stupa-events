"""Public routes of the mail and profile subscriptions (B3-KONTRAKT 3.1 to 3.4).

No route sets a cookie or reads one; tokens travel in the body or in `X-Subscription-Token`,
never in a query string. Answers depending on an address (sign-up, magic link, confirmation)
run inside `limits.padded`, so a known and an unknown address take equally long and answer
alike. Tokens and addresses never reach a log.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.provider import mail_queue_from_pool
from app.modules.notifications.queue import MailQueue, NullMailQueue
from app.modules.subscriptions import consent, doi, limits, manage
from app.modules.subscriptions.db import get_subs_session
from app.modules.subscriptions.interests import Catalog, load_catalog
from app.modules.subscriptions.problems import InvalidTokenError, invalid_token_response
from app.modules.subscriptions.schemas import (
    ConfirmOut,
    ConfirmPreviewOut,
    ConsentOut,
    ManageLinkIn,
    MeUpdate,
    Question,
    QuestionnaireOut,
    QuestionOption,
    RotatedIcsOut,
    SubscribeIn,
    SubscribeOut,
    SubscriptionMeOut,
    TokenIn,
)
from app.shared.antiabuse import (
    AltchaDep,
    RateLimiterDep,
    SettingsDep,
    body_cap,
    client_ip,
    verify_altcha_solution,
)
from app.shared.errors import ProblemDetail, ServiceUnavailableError

SubsSession = Annotated[AsyncSession, Depends(get_subs_session)]
TokenHeader = Annotated[str | None, Header(alias="X-Subscription-Token")]
_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_COMMON: dict[int | str, dict[str, Any]] = {413: _PROBLEM, 503: _PROBLEM}
_TOKEN_404: dict[int | str, dict[str, Any]] = {404: _PROBLEM}
QUESTIONS_CACHE = "public, max-age=300"


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _ready(settings: SettingsDep) -> None:
    if not settings.subs_keys_enabled:
        raise ServiceUnavailableError("Mail subscriptions are not configured.")


router = APIRouter(prefix="/public", tags=["subscriptions"], dependencies=[Depends(_no_store)])
posts = [Depends(_ready), Depends(body_cap("subs_body_max_bytes"))]


async def mail_queue(request: Request) -> MailQueue:
    """Return the queue for system mails (a dropping one while Redis is missing)."""
    pool = getattr(request.app.state, "arq_pool", None)
    return mail_queue_from_pool(pool) or NullMailQueue()


QueueDep = Annotated[MailQueue, Depends(mail_queue)]


def build_questionnaire(catalog: Catalog) -> QuestionnaireOut:
    """Build the questionnaire (version 1, five questions) from the catalog."""
    interests = [QuestionOption(value=i.slug, label=i.label) for i in catalog.interests.values()]
    faculties = [QuestionOption(value=v, label=c.name) for v, c in catalog.faculties().items()]
    channels = [
        QuestionOption(value="calendar", label="Nur Kalender"),
        QuestionOption(value="mail", label="Kalender und Mail"),
    ]
    return QuestionnaireOut(
        version=doi.QUESTIONNAIRE_VERSION,
        questions=[
            Question(
                id="interests",
                prompt="Was interessiert dich?",
                type="multi",
                required=True,
                options=interests,
            ),
            Question(
                id="meetings",
                prompt="Interessieren dich Sitzungen und Gremien?",
                type="boolean",
                required=True,
            ),
            Question(
                id="faculty",
                prompt="Zu welcher Fachschaft gehörst du?",
                type="single",
                required=False,
                options=faculties,
            ),
            Question(
                id="channel",
                prompt="Wie möchtest du auf dem Laufenden bleiben?",
                type="single",
                required=True,
                options=channels,
            ),
            Question(id="mail", prompt="Adresse und Einwilligung", type="mail", required=False),
        ],
        consent=ConsentOut(
            version=consent.CURRENT_VERSION,
            template=consent.TEMPLATES[consent.CURRENT_VERSION],
            privacy_url=consent.PRIVACY_URL,
        ),
    )


@router.get("/getstarted/questions", response_model=QuestionnaireOut, responses=_COMMON)
async def questions(
    request: Request, response: Response, session: SubsSession
) -> QuestionnaireOut | Response:
    """Return the questionnaire; the same for everybody, so it may be cached."""
    out = build_questionnaire(await load_catalog(session))
    etag = f'"{sha256(out.model_dump_json().encode()).hexdigest()[:32]}"'
    headers = {"ETag": etag, "Cache-Control": QUESTIONS_CACHE}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    response.headers.update(headers)
    return out


@router.post(
    "/subscriptions",
    status_code=202,
    response_model=SubscribeOut,
    dependencies=posts,
    responses={**_COMMON, 400: _PROBLEM, 409: _PROBLEM, 422: _PROBLEM, 429: _PROBLEM},
)
async def subscribe(
    body: SubscribeIn,
    request: Request,
    session: SubsSession,
    settings: SettingsDep,
    limiter: RateLimiterDep,
    verifier: AltchaDep,
    queue: QueueDep,
) -> SubscribeOut:
    """Create a profile and, when asked, start the double opt-in; always 202."""
    async with limits.padded(settings.min_response_seconds):
        await verify_altcha_solution(verifier, body.altcha)
        await limits.hit_ip(limiter, "ip", client_ip(request), limit=settings.rl_subs_ip_per_hour)
        catalog = await load_catalog(session)
        registration = await doi.subscribe(session, settings, limiter, catalog, body)
        if registration.message is not None:
            await queue.enqueue(registration.message)
        return registration.out


@router.post(
    "/subscriptions/confirm/preview",
    response_model=ConfirmPreviewOut,
    dependencies=posts,
    responses={**_COMMON, **_TOKEN_404, 429: _PROBLEM},
)
async def confirm_preview(
    body: TokenIn,
    request: Request,
    session: SubsSession,
    settings: SettingsDep,
    limiter: RateLimiterDep,
) -> ConfirmPreviewOut | Response:
    """Name the categories behind a confirmation token without changing anything."""
    async with limits.padded(settings.min_response_seconds):
        await limits.hit_ip(
            limiter, "confirm", client_ip(request), limit=settings.rl_subs_confirm_per_hour
        )
        try:
            catalog = await load_catalog(session)
            return ConfirmPreviewOut(categories=await doi.preview(session, catalog, body.token))
        except InvalidTokenError:
            return invalid_token_response()


@router.post(
    "/subscriptions/confirm",
    response_model=ConfirmOut,
    dependencies=posts,
    responses={**_COMMON, **_TOKEN_404, 429: _PROBLEM},
)
async def confirm(
    body: TokenIn,
    request: Request,
    session: SubsSession,
    settings: SettingsDep,
    limiter: RateLimiterDep,
) -> ConfirmOut | Response:
    """Confirm the subscription: the click on the button of the confirmation page."""
    async with limits.padded(settings.min_response_seconds):
        await limits.hit_ip(
            limiter, "confirm", client_ip(request), limit=settings.rl_subs_confirm_per_hour
        )
        try:
            await doi.confirm(session, body.token)
        except InvalidTokenError:
            return invalid_token_response()
        return ConfirmOut(status="confirmed")


@router.post(
    "/subscriptions/manage-link",
    status_code=202,
    response_model=dict[str, Any],
    dependencies=posts,
    responses={**_COMMON, 400: _PROBLEM, 422: _PROBLEM, 429: _PROBLEM},
)
async def manage_link(
    body: ManageLinkIn,
    request: Request,
    session: SubsSession,
    settings: SettingsDep,
    limiter: RateLimiterDep,
    verifier: AltchaDep,
    queue: QueueDep,
) -> dict[str, Any]:
    """Mail a management link to a confirmed address; always 202 with an empty body."""
    async with limits.padded(settings.min_response_seconds):
        await verify_altcha_solution(verifier, body.altcha)
        await limits.hit_ip(limiter, "ip", client_ip(request), limit=settings.rl_subs_ip_per_hour)
        message = await manage.request_link(session, settings, limiter, body.email)
        if message is not None:
            await queue.enqueue(message)
        return {}


async def _owner(
    request: Request,
    session: AsyncSession,
    settings: SettingsDep,
    limiter: RateLimiterDep,
    token: str | None,
    *,
    lock: bool = False,
) -> manage.Owner:
    await limits.hit_ip(limiter, "me", client_ip(request), limit=settings.rl_subs_me_per_hour)
    return await manage.owner_of(session, token, lock=lock)


@router.get(
    "/subscriptions/me",
    response_model=SubscriptionMeOut,
    dependencies=[Depends(_ready)],
    responses={**_COMMON, **_TOKEN_404, 429: _PROBLEM},
)
async def me(
    request: Request,
    session: SubsSession,
    settings: SettingsDep,
    limiter: RateLimiterDep,
    token: TokenHeader = None,
) -> SubscriptionMeOut | Response:
    """Show the interests and the mail switch behind a management token."""
    try:
        owner = await _owner(request, session, settings, limiter, token)
    except InvalidTokenError:
        return invalid_token_response()
    return await manage.show(session, await load_catalog(session), owner)


@router.put(
    "/subscriptions/me",
    response_model=SubscriptionMeOut,
    dependencies=posts,
    responses={**_COMMON, **_TOKEN_404, 422: _PROBLEM},
)
async def update_me(
    body: MeUpdate,
    request: Request,
    session: SubsSession,
    settings: SettingsDep,
    limiter: RateLimiterDep,
    token: TokenHeader = None,
) -> SubscriptionMeOut | Response:
    """Change the interests and/or switch the mail on or off."""
    try:
        owner = await _owner(request, session, settings, limiter, token, lock=True)
    except InvalidTokenError:
        return invalid_token_response()
    return await manage.update_me(session, await load_catalog(session), owner, body)


@router.post(
    "/subscriptions/me/ics-token",
    response_model=RotatedIcsOut,
    dependencies=posts,
    responses={**_COMMON, **_TOKEN_404, 429: _PROBLEM},
)
async def rotate_ics_token(
    request: Request,
    session: SubsSession,
    settings: SettingsDep,
    limiter: RateLimiterDep,
    token: TokenHeader = None,
) -> RotatedIcsOut | Response:
    """Rotate the calendar token; the new address is in the answer once."""
    try:
        owner = await _owner(request, session, settings, limiter, token, lock=True)
    except InvalidTokenError:
        return invalid_token_response()
    return await manage.rotate_ics(session, settings, owner)


@router.delete(
    "/subscriptions/me",
    status_code=204,
    dependencies=[Depends(_ready)],
    responses={**_COMMON, **_TOKEN_404, 429: _PROBLEM},
)
async def delete_me(
    request: Request,
    session: SubsSession,
    settings: SettingsDep,
    limiter: RateLimiterDep,
    token: TokenHeader = None,
) -> Response:
    """Unsubscribe and erase the address, the profile and the tokens."""
    try:
        owner = await _owner(request, session, settings, limiter, token, lock=True)
    except InvalidTokenError:
        return invalid_token_response()
    await manage.erase(session, owner)
    return Response(status_code=204)
