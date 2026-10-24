"""The management page behind the magic link: look, change interests, rotate, delete.

The token is the proof of the mailbox: it is looked up by its SHA-256 digest, must belong to
a `confirmed` subscriber and must not be expired; every other case is the same
`InvalidTokenError`. The link does not extend itself. Changing the interests rewrites the
consent proof only when mail would reach a category the person never agreed to; then the page
shows the sentence and the request carries its version and the tick (`consent_required`). A
narrower choice leaves the proof as it is. Changes reach Listmonk through the outbox.
Deleting calls the `privacy_*` function and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.mail import MailMessage
from app.modules.subscriptions import consent, doi, emailkey, limits, mails, profiles, tokens
from app.modules.subscriptions.enqueue import enqueue_outbox
from app.modules.subscriptions.interests import Catalog
from app.modules.subscriptions.models import Subscriber, SubscriptionProfile
from app.modules.subscriptions.problems import InvalidTokenError
from app.modules.subscriptions.schemas import ConsentIn, MeUpdate, RotatedIcsOut, SubscriptionMeOut
from app.settings import Settings
from app.shared.errors import ConflictError, NotFoundError, ValidationProblem
from app.shared.ratelimit import RateLimiter


@dataclass(frozen=True, slots=True)
class Owner:
    """The subscriber behind a valid management token and their profile (if any)."""

    subscriber_id: UUID
    profile_id: UUID | None


async def owner_of(session: AsyncSession, token: str | None, *, lock: bool = False) -> Owner:
    """Find the subscriber of a management token.

    Raises:
        InvalidTokenError: The token is missing, malformed, unknown, expired or revoked.
    """
    if token is None or not tokens.is_well_formed(token):
        token = tokens.new_token()
    query = (
        select(Subscriber.id, SubscriptionProfile.id.label("profile_id"))
        .outerjoin(SubscriptionProfile, SubscriptionProfile.subscriber_id == Subscriber.id)
        .where(
            Subscriber.manage_token_hash == tokens.hash_token(token),
            Subscriber.manage_expires_at > func.now(),
            Subscriber.status == "confirmed",
        )
    )
    row = (await session.execute(query.with_for_update(of=Subscriber) if lock else query)).first()
    if row is None:
        raise InvalidTokenError
    return Owner(row.id, row.profile_id)


async def show(session: AsyncSession, catalog: Catalog, owner: Owner) -> SubscriptionMeOut:
    """Return the management view of the owner."""
    row = None
    if owner.profile_id is not None:
        row = (
            await session.execute(
                select(
                    SubscriptionProfile.interests,
                    SubscriptionProfile.categories,
                    SubscriptionProfile.mail_enabled,
                ).where(SubscriptionProfile.id == owner.profile_id)
            )
        ).first()
    if row is None:
        return SubscriptionMeOut(interests=[], categories=[], mail_enabled=False, has_profile=False)
    return SubscriptionMeOut(
        interests=list(row.interests),
        categories=profiles.category_refs(catalog, row.categories),
        mail_enabled=row.mail_enabled,
        has_profile=True,
    )


async def _record_consent(
    session: AsyncSession, owner: Owner, given: ConsentIn | None, categories: list[str]
) -> None:
    if given is None or not given.accepted:
        raise ValidationProblem("Bitte bestätige die Einwilligung.", code="consent_required")
    if given.version != consent.CURRENT_VERSION:
        raise ConflictError("Der Einwilligungstext hat sich geändert.", code="consent_outdated")
    await session.execute(
        update(Subscriber)
        .where(Subscriber.id == owner.subscriber_id)
        .values(
            consent_text_version=consent.CURRENT_VERSION,
            consent_categories=categories,
            consent_at=func.now(),
            updated_at=func.now(),
        )
    )


async def update_me(
    session: AsyncSession, catalog: Catalog, owner: Owner, change: MeUpdate
) -> SubscriptionMeOut:
    """Apply new interests and/or the mail switch; queue the Listmonk upsert; commit.

    Raises:
        ValidationProblem: Empty change, unknown interest or no interest at all.
        NotFoundError: The person has no profile to change.
    """
    if change.interests is None and change.mail_enabled is None:
        raise ValidationProblem("Nichts zu ändern.", code="validation_error")
    if owner.profile_id is None:
        raise NotFoundError("Kein Profil.", code="no_profile")
    current = (
        await session.execute(
            select(
                SubscriptionProfile.categories,
                SubscriptionProfile.mail_enabled,
                Subscriber.consent_categories,
            )
            .join(Subscriber, Subscriber.id == SubscriptionProfile.subscriber_id)
            .where(SubscriptionProfile.id == owner.profile_id)
        )
    ).one()
    values: dict[str, object] = {"updated_at": func.now()}
    categories = list(current.categories)
    if change.interests is not None:
        resolution = doi.resolve_interests(catalog, change.interests)
        categories = list(resolution.categories)
        values |= {"interests": list(resolution.interests), "categories": categories}
    mail_enabled = current.mail_enabled if change.mail_enabled is None else change.mail_enabled
    if change.mail_enabled is not None:
        values["mail_enabled"] = change.mail_enabled
    if mail_enabled and not set(categories) <= set(current.consent_categories):
        await _record_consent(session, owner, change.consent, categories)
    await session.execute(
        update(SubscriptionProfile)
        .where(SubscriptionProfile.id == owner.profile_id)
        .values(**values)
    )
    await enqueue_outbox(session, op="upsert", subscriber_id=owner.subscriber_id)
    await session.commit()
    return await show(session, catalog, owner)


async def rotate_ics(session: AsyncSession, settings: Settings, owner: Owner) -> RotatedIcsOut:
    """Give the profile a new calendar token and return the new address once; commit.

    Raises:
        NotFoundError: The person has no profile.
    """
    if owner.profile_id is None:
        raise NotFoundError("Kein Profil.", code="no_profile")
    token = await profiles.rotate_token(session, owner.profile_id)
    await session.commit()
    ics_url, webcal_url = profiles.calendar_urls(settings, token)
    return RotatedIcsOut(ics_url=ics_url, webcal_url=webcal_url)


async def erase(session: AsyncSession, owner: Owner) -> None:
    """Erase the subscriber, the profile and the tokens; commit."""
    await session.execute(text("SELECT privacy_erase_subscriber(:id)"), {"id": owner.subscriber_id})
    await session.commit()


async def request_link(
    session: AsyncSession, settings: Settings, limiter: RateLimiter, address: str
) -> MailMessage | None:
    """Issue a management token for a confirmed address and return the mail; commit.

    Any other address state does nothing and returns `None`: the caller answers the same.

    Raises:
        ValidationProblem: `invalid_email`.
    """
    assert settings.email_hash_key is not None
    canonical = doi.canonical_or_422(address)
    may_mail = await limits.address_allowed(
        limiter, settings, emailkey.limit_hmac(settings.email_hash_key, canonical)
    )
    found = await doi.lock_address(
        session, emailkey.identity_hmac(settings.email_hash_key, canonical)
    )
    message = None
    if found is not None and found[1] == "confirmed":
        token, token_hash = await doi.issue_manage_token(session, found[0])
        if may_mail and await limits.claim_mail_slot(session, settings, found[0]):
            message = mails.manage_link_mail(
                settings, to=canonical, subscriber_id=found[0], token=token, token_hash=token_hash
            )
    await session.commit()
    return message
