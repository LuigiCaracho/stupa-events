"""Wire shapes of the public subscription routes (camelCase, unknown fields refused).

Every request model is small and bounded; the body cap of the routes (4 KiB) is the outer
limit. Responses never carry an address, a token hash or a status of an address.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.modules.auth.schemas import CamelModel

Slug = Annotated[str, StringConstraints(min_length=1, max_length=60)]
TokenText = Annotated[str, StringConstraints(min_length=1, max_length=200)]
AltchaText = Annotated[str, StringConstraints(max_length=4096)]


class QuestionOption(CamelModel):
    """One answer of a choice question."""

    value: str
    label: str


class Question(CamelModel):
    """One question of the questionnaire."""

    id: Literal["interests", "meetings", "faculty", "channel", "mail"]
    prompt: str
    type: Literal["multi", "boolean", "single", "mail"]
    required: bool
    options: list[QuestionOption] | None = None


class ConsentOut(CamelModel):
    """The current consent sentence with its version."""

    version: str
    template: str
    privacy_url: str


class QuestionnaireOut(CamelModel):
    """The questionnaire: version, questions and the consent text."""

    version: int
    questions: list[Question]
    consent: ConsentOut


class ProfileCategory(CamelModel):
    """A category by slug and name."""

    slug: str
    name: str


class ProfileOut(CamelModel):
    """The new profile: its calendar address (shown once) and the categories."""

    ics_url: str
    webcal_url: str
    categories: list[ProfileCategory]


class MailRequestedOut(CamelModel):
    """Whether the person asked for mail; never whether the address was known."""

    requested: bool


class SubscribeOut(CamelModel):
    """Answer of `POST /subscriptions`; the same for every address state."""

    profile: ProfileOut
    mail: MailRequestedOut


class AnswersIn(CamelModel):
    """The answers of the questionnaire."""

    interests: list[Slug] = Field(max_length=40)
    meetings: bool
    faculty: Slug | None = None
    mail: bool


class ConsentIn(CamelModel):
    """The consent the person gave: the version of the sentence they saw."""

    version: Annotated[str, StringConstraints(max_length=40)]
    accepted: bool


class SubscribeIn(CamelModel):
    """Body of `POST /subscriptions`."""

    questionnaire_version: int
    answers: AnswersIn
    email: Annotated[str, StringConstraints(max_length=320)] | None = None
    consent: ConsentIn | None = None
    altcha: AltchaText = ""


class TokenIn(CamelModel):
    """A single token in the body (confirmation)."""

    token: TokenText


class ConfirmPreviewOut(CamelModel):
    """What the confirmation page shows before the button: the category names."""

    categories: list[str]


class ConfirmOut(CamelModel):
    """Result of the confirmation."""

    status: Literal["confirmed"]


class ManageLinkIn(CamelModel):
    """Body of `POST /manage-link`."""

    email: Annotated[str, StringConstraints(max_length=320)]
    altcha: AltchaText = ""


class SubscriptionMeOut(CamelModel):
    """The management page: interests, categories, the mail switch."""

    interests: list[str]
    categories: list[ProfileCategory]
    mail_enabled: bool
    ics_url: None = None
    has_profile: bool


class MeUpdate(CamelModel):
    """Body of `PUT /me`; at least one field."""

    interests: list[Slug] | None = Field(default=None, max_length=40)
    mail_enabled: bool | None = None


class RotatedIcsOut(CamelModel):
    """The new calendar address, shown once."""

    ics_url: str
    webcal_url: str
