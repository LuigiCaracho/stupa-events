"""Sign-up and the double opt-in: register an address, send the proof request, confirm.

One code path serves every address state (PLAN 18, minor 2): the same checks, the same
transaction shape and the same answer, whether the address is new, pending, subscribed,
unsubscribed, bounced or erased (erased rows have no address and look new). A subscribed
address changes nothing and gets a note with a management link, so nobody can add foreign
addresses to more lists. Consent is the proof of the person's own click: the confirm call
(a POST from the page, never a GET) sets `confirmed_at`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.mail import MailMessage
from app.modules.subscriptions import consent, emailkey, limits, mails, profiles, tokens
from app.modules.subscriptions.enqueue import enqueue_outbox
from app.modules.subscriptions.interests import (
    Catalog,
    NoInterestError,
    Resolution,
    TooManyCategoriesError,
    UnknownInterestError,
    resolve_categories,
)
from app.modules.subscriptions.models import Subscriber, SubscriptionProfile
from app.modules.subscriptions.problems import InvalidTokenError
from app.modules.subscriptions.schemas import (
    MailRequestedOut,
    ProfileOut,
    SubscribeIn,
    SubscribeOut,
)
from app.settings import Settings
from app.shared.errors import ConflictError, FieldError, ValidationProblem
from app.shared.ratelimit import RateLimiter

QUESTIONNAIRE_VERSION = 1
_REOPENABLE = ("pending", "unsubscribed", "bounced")


@dataclass(frozen=True, slots=True)
class Registration:
    """The outcome of a sign-up: the answer and the mail to queue after the commit."""

    out: SubscribeOut
    message: MailMessage | None


def resolve_interests(
    catalog: Catalog, interests: list[str], meetings: bool = False, faculty: str | None = None
) -> Resolution:
    """Resolve answers or a list of interests, or raise the matching 422.

    Raises:
        ValidationProblem: `unknown_interest` or `no_interest`.
    """
    try:
        return resolve_categories(catalog, interests, meetings, faculty)
    except UnknownInterestError as exc:
        raise ValidationProblem(
            "Unbekanntes Interesse.",
            code="unknown_interest",
            errors=[FieldError(field="answers.interests", msg="unknown interest")],
        ) from exc
    except (NoInterestError, TooManyCategoriesError) as exc:
        raise ValidationProblem("Wähl mindestens ein Interesse.", code="no_interest") from exc


def canonical_or_422(address: str) -> str:
    """Return the canonical address.

    Raises:
        ValidationProblem: `invalid_email`.
    """
    try:
        return emailkey.canonicalize(address)
    except emailkey.InvalidEmailError as exc:
        raise ValidationProblem(
            "Das sieht nicht wie eine Mailadresse aus.",
            code="invalid_email",
            errors=[FieldError(field="email", msg="invalid")],
        ) from exc


def check_request(body: SubscribeIn) -> str | None:
    """Check the parts that depend only on the request; return the canonical address.

    Raises:
        ValidationProblem: Mail asked for without address or consent, or the other way round,
            `consent_required`, `invalid_email`.
        ConflictError: `consent_outdated` or `questionnaire_outdated`.
    """
    if body.questionnaire_version != QUESTIONNAIRE_VERSION:
        raise ConflictError("Der Fragebogen hat sich geändert.", code="questionnaire_outdated")
    if not body.answers.mail:
        if body.email is not None or body.consent is not None:
            raise ValidationProblem("Ohne Mail keine Adresse.", code="validation_error")
        return None
    if body.email is None or body.consent is None:
        raise ValidationProblem("Adresse und Einwilligung fehlen.", code="validation_error")
    if body.consent.version != consent.CURRENT_VERSION:
        raise ConflictError("Der Einwilligungstext hat sich geändert.", code="consent_outdated")
    if not body.consent.accepted:
        raise ValidationProblem("Bitte bestätige die Einwilligung.", code="consent_required")
    return canonical_or_422(body.email)


async def lock_address(session: AsyncSession, address_hmac: str) -> tuple[UUID, str] | None:
    row = (
        await session.execute(
            select(Subscriber.id, Subscriber.status)
            .where(Subscriber.email_hmac == address_hmac)
            .with_for_update()
        )
    ).first()
    return None if row is None else (row.id, row.status)


async def _insert_pending(
    session: AsyncSession,
    settings: Settings,
    *,
    canonical: str,
    address_hmac: str,
    token_hash: str,
    categories: list[str],
) -> UUID | None:
    assert settings.pgcrypto_email_key is not None
    result = await session.execute(
        pg_insert(Subscriber)
        .values(
            email_enc=emailkey.encrypt(canonical, settings.pgcrypto_email_key),
            email_hmac=address_hmac,
            status="pending",
            confirm_token_hash=token_hash,
            confirm_expires_at=func.now() + timedelta(hours=tokens.CONFIRM_TTL_HOURS),
            consent_text_version=consent.CURRENT_VERSION,
            consent_categories=categories,
            consent_at=func.now(),
        )
        .on_conflict_do_nothing(index_elements=[Subscriber.email_hmac])
        .returning(Subscriber.id)
    )
    return result.scalar()


async def _rearm(
    session: AsyncSession, subscriber_id: UUID, token_hash: str, categories: list[str]
) -> None:
    await session.execute(
        update(Subscriber)
        .where(Subscriber.id == subscriber_id)
        .values(
            confirm_token_hash=token_hash,
            confirm_expires_at=func.now() + timedelta(hours=tokens.CONFIRM_TTL_HOURS),
            consent_text_version=consent.CURRENT_VERSION,
            consent_categories=categories,
            consent_at=func.now(),
            updated_at=func.now(),
        )
    )


async def _link_profile(session: AsyncSession, subscriber_id: UUID, profile_id: UUID) -> None:
    await session.execute(
        update(SubscriptionProfile)
        .where(SubscriptionProfile.subscriber_id == subscriber_id)
        .values(subscriber_id=None, mail_enabled=False)
    )
    await session.execute(
        update(SubscriptionProfile)
        .where(SubscriptionProfile.id == profile_id)
        .values(subscriber_id=subscriber_id)
    )


async def issue_manage_token(session: AsyncSession, subscriber_id: UUID) -> tuple[str, str]:
    """Set a fresh management token (valid 2 h) and return it with its hash."""
    token = tokens.new_token()
    token_hash = tokens.hash_token(token)
    await session.execute(
        update(Subscriber)
        .where(Subscriber.id == subscriber_id)
        .values(
            manage_token_hash=token_hash,
            manage_expires_at=func.now() + timedelta(hours=tokens.MANAGE_TTL_HOURS),
            updated_at=func.now(),
        )
    )
    return token, token_hash


async def _find_or_create(
    session: AsyncSession,
    settings: Settings,
    *,
    canonical: str,
    address_hmac: str,
    token_hash: str,
    categories: list[str],
) -> tuple[UUID, str, bool]:
    """Lock the row of the address, creating a pending one; return id, status, created."""
    found = await lock_address(session, address_hmac)
    if found is not None:
        return found[0], found[1], False
    created = await _insert_pending(
        session,
        settings,
        canonical=canonical,
        address_hmac=address_hmac,
        token_hash=token_hash,
        categories=categories,
    )
    if created is not None:
        return created, "pending", True
    raced = await lock_address(session, address_hmac)
    assert raced is not None
    return raced[0], raced[1], False


async def _register_address(
    session: AsyncSession,
    settings: Settings,
    limiter: RateLimiter,
    catalog: Catalog,
    *,
    canonical: str,
    profile_id: UUID,
    resolution: Resolution,
) -> MailMessage | None:
    assert settings.email_hash_key is not None
    address_hmac = emailkey.identity_hmac(settings.email_hash_key, canonical)
    may_mail = await limits.address_allowed(
        limiter, settings, emailkey.limit_hmac(settings.email_hash_key, canonical)
    )
    token = tokens.new_token()
    token_hash = tokens.hash_token(token)
    categories = list(resolution.categories)
    sid, status, created = await _find_or_create(
        session,
        settings,
        canonical=canonical,
        address_hmac=address_hmac,
        token_hash=token_hash,
        categories=categories,
    )
    reopen = status in _REOPENABLE
    if reopen:
        if not created:
            await _rearm(session, sid, token_hash, categories)
        await _link_profile(session, sid, profile_id)
    else:
        token, token_hash = await issue_manage_token(session, sid)
    if not (may_mail and await limits.claim_mail_slot(session, settings, sid)):
        return None
    if reopen:
        labels = [catalog.label(i) for i in resolution.interests]
        return mails.doi_mail(
            settings,
            to=canonical,
            subscriber_id=sid,
            token=token,
            token_hash=token_hash,
            categories=labels,
        )
    return mails.already_mail(
        settings, to=canonical, subscriber_id=sid, token=token, token_hash=token_hash
    )


async def subscribe(
    session: AsyncSession,
    settings: Settings,
    limiter: RateLimiter,
    catalog: Catalog,
    body: SubscribeIn,
) -> Registration:
    """Create the profile and, with mail, register the address; commit.

    Raises:
        ValidationProblem: The answers or the address are unusable.
        ConflictError: The questionnaire or the consent text is outdated.
    """
    canonical = check_request(body)
    answers = body.answers
    resolution = resolve_interests(catalog, answers.interests, answers.meetings, answers.faculty)
    profile_id, token = await profiles.create_profile(
        session, resolution, body.questionnaire_version
    )
    message = None
    if canonical is not None:
        message = await _register_address(
            session,
            settings,
            limiter,
            catalog,
            canonical=canonical,
            profile_id=profile_id,
            resolution=resolution,
        )
    await session.commit()
    ics_url, webcal_url = profiles.calendar_urls(settings, token)
    out = SubscribeOut(
        profile=ProfileOut(
            ics_url=ics_url,
            webcal_url=webcal_url,
            categories=profiles.category_refs(catalog, resolution.categories),
        ),
        mail=MailRequestedOut(requested=body.answers.mail),
    )
    return Registration(out, message)


async def preview(session: AsyncSession, catalog: Catalog, token: str) -> list[str]:
    """Return the interest labels behind a confirmation token; change nothing.

    Raises:
        InvalidTokenError: Unknown, expired or used token.
    """
    row = (
        await session.execute(
            select(SubscriptionProfile.interests)
            .join(Subscriber, Subscriber.id == SubscriptionProfile.subscriber_id)
            .where(
                Subscriber.confirm_token_hash == tokens.hash_token(token),
                Subscriber.confirm_expires_at > func.now(),
                Subscriber.status.in_(_REOPENABLE),
            )
        )
    ).first()
    if row is None:
        raise InvalidTokenError
    return [catalog.label(i) for i in row.interests if _known(catalog, i)]


def _known(catalog: Catalog, interest: str) -> bool:
    return interest in catalog.interests or interest in catalog.faculties()


async def confirm(session: AsyncSession, token: str) -> None:
    """Confirm the subscription of the token's address; queue the Listmonk upsert; commit.

    A previously unsubscribed or bounced address becomes `confirmed` again here and only here;
    the queued upsert carries `reconfirmed` so the worker lifts the old blocklist entry.

    Raises:
        InvalidTokenError: Unknown, expired or used token.
    """
    row = (
        await session.execute(
            select(Subscriber.id, Subscriber.status)
            .where(
                Subscriber.confirm_token_hash == tokens.hash_token(token),
                Subscriber.confirm_expires_at > func.now(),
                Subscriber.status.in_(_REOPENABLE),
            )
            .with_for_update()
        )
    ).first()
    if row is None:
        raise InvalidTokenError
    await session.execute(
        update(Subscriber)
        .where(Subscriber.id == row.id)
        .values(
            status="confirmed",
            confirmed_at=func.now(),
            unsubscribed_at=None,
            confirm_token_hash=None,
            confirm_expires_at=None,
            updated_at=func.now(),
        )
    )
    await session.execute(
        update(SubscriptionProfile)
        .where(SubscriptionProfile.subscriber_id == row.id)
        .values(mail_enabled=True, updated_at=func.now())
    )
    payload = None if row.status == "pending" else {"reconfirmed": True}
    await enqueue_outbox(session, op="upsert", subscriber_id=row.id, payload=payload)
    await session.commit()
