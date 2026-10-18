"""Guards of the pipeline as pure functions `(snapshot, actor, now) -> list[Reason]`.

An empty list means the guard holds. The service shows all reasons before the click and
refuses a transition with the first blocker (PLAN 4.4). The order of the `reasons[]` is
the order of the guard table in the M3 contract, 2.3.
"""

from app.modules.pipeline.guards.common import FIELD_NAMES, Guard, system_only
from app.modules.pipeline.guards.content import (
    checklist_done,
    facts_valid,
    howto_verified,
    location_confirmed,
    no_open_comment_on_hero,
    no_open_duplicate,
    open_comment_required,
    outcome_set_or_waived,
    retrospective_filled,
    title_clean,
)
from app.modules.pipeline.guards.fields import (
    PROPOSAL_QUOTA,
    date_in_future,
    has_field,
    organization_scope_or_proposal,
    proposal_quota,
    venue_or_text,
)
from app.modules.pipeline.guards.media import (
    attachments_scanned,
    flyer_date_confirmed,
    image_or_exception,
    rights_complete,
)
from app.modules.pipeline.guards.timing import (
    end_estimated,
    ended_more_than,
    followup_older_than,
    four_eyes,
    human_approval,
    long_running,
    origin_is,
    publish_at_reached,
    wall_clock_ok,
)

__all__ = [
    "FIELD_NAMES",
    "PROPOSAL_QUOTA",
    "Guard",
    "attachments_scanned",
    "checklist_done",
    "date_in_future",
    "end_estimated",
    "ended_more_than",
    "facts_valid",
    "flyer_date_confirmed",
    "followup_older_than",
    "four_eyes",
    "has_field",
    "howto_verified",
    "human_approval",
    "image_or_exception",
    "location_confirmed",
    "long_running",
    "no_open_comment_on_hero",
    "no_open_duplicate",
    "open_comment_required",
    "organization_scope_or_proposal",
    "origin_is",
    "outcome_set_or_waived",
    "proposal_quota",
    "publish_at_reached",
    "retrospective_filled",
    "rights_complete",
    "system_only",
    "title_clean",
    "venue_or_text",
    "wall_clock_ok",
]
