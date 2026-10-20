"""Property: no sequence of steps publishes without a poster, an exception or a person.

The state machine drives the pure `decide` function the way the service does and applies
the columns of `transition_values`. It changes the poster and the exception in arbitrary
order and also runs the worker (`due_transition` and `decide` with the system actor) and
the public-status actions. Field writes and reverts run through `plan_patch`, and a revert only
in `REVERTIBLE` states; the content of `approved` stays as at the approval. Invariants: nothing reaches `approved` or `live` without a
valid poster or exception at entry; `live` always has a human approver; the worker fires
only T05, T08, T08b and T09b; the public status differs from `scheduled` only from `live`
on; REST, worker and factory path reach the same image decision.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from app.modules.pipeline.actions_service import PUBLIC_TO, next_public_status
from app.modules.pipeline.advance import AdvanceRow, due_transition
from app.modules.pipeline.decision import decide
from app.modules.pipeline.fieldclass import plan_patch
from app.modules.pipeline.revert import REVERTIBLE
from app.modules.pipeline.snapshot import PosterSnapshot
from app.modules.pipeline.transitions import TRANSITIONS
from app.modules.pipeline.values import transition_values
from tests.unit.pipeline.support import NOW, actor, snap

ROLES = ["submitter", "organizer", "approver", "editor", "admin", "stupa", "member", "viewer"]
SYSTEM_TRANSITIONS = {"T05", "T08", "T08b", "T09b"}
PUBLISHED = {"approved", "live"}
POSTERS = st.one_of(
    st.none(),
    st.builds(
        PosterSnapshot,
        scan_status=st.sampled_from(["pending", "clean", "infected", "error"]),
        has_derivatives=st.booleans(),
        alt_text=st.sampled_from([None, "", "Alt"]),
        credit=st.sampled_from([None, "", "Foto: Ada"]),
        rights_basis=st.sampled_from(["unknown", "own_work", "license"]),
    ),
)


def has_image(snapshot) -> bool:  # noqa: ANN001
    poster = snapshot.poster
    return bool(snapshot.image_exception_reason) or (poster is not None and poster.usable)


def has_image_file(snapshot) -> bool:  # noqa: ANN001
    poster = snapshot.poster
    return bool(snapshot.image_exception_reason) or (poster is not None and poster.usable_media)


class PipelineMachine(RuleBasedStateMachine):
    """A dossier moved by random people and by the worker while its poster changes."""

    def __init__(self) -> None:
        super().__init__()
        self.snapshot = snap(state="idea", poster=None, created_by="x")
        self.now = NOW
        self.title_at_approval: str | None = None
        self.counter = 0

    def _apply(self, tid: str, who) -> None:  # noqa: ANN001
        transition = TRANSITIONS[tid]
        values = transition_values(
            transition,
            actor_sub=who.sub,
            rev=self.snapshot.rev,
            public_seq=0,
            publish_at=None,
            slug="slug",
        )
        names = {"state", "submitted_by", "approved_by", "publish_at", "public_status"}
        self.snapshot = replace(
            self.snapshot,
            **{k: v for k, v in values.items() if k in names},
            rev=self.snapshot.rev + 1,
        )
        if self.snapshot.state == "approved":
            self.title_at_approval = self.snapshot.title

    @rule(poster=POSTERS)
    def set_poster(self, poster: PosterSnapshot | None) -> None:
        self.snapshot = replace(self.snapshot, poster=poster)
        if self.snapshot.state in PUBLISHED and not has_image(self.snapshot):
            self.snapshot = replace(self.snapshot, poster=None)
            self.snapshot = replace(self.snapshot, image_exception_reason="Hochschulveranstaltung")

    @rule(reason=st.sampled_from([None, "short", "Hochschulveranstaltung ohne Motiv"]))
    def grant_exception(self, reason: str | None) -> None:
        if (
            reason
            and len(reason) >= 10
            and self.snapshot.state in {"idea", "planning", "in_review", "approved"}
        ):
            self.snapshot = replace(self.snapshot, image_exception_reason=reason)

    @rule(
        tid=st.sampled_from(sorted(TRANSITIONS)),
        role=st.sampled_from(ROLES),
        late=st.booleans(),
        note=st.booleans(),
        publish_at=st.booleans(),
    )
    def fire(self, tid: str, role: str, late: bool, note: bool, publish_at: bool) -> None:
        now = self.now + (timedelta(days=30) if late else timedelta(0))
        who = actor(role, sub="x" if role != "organizer" else "y")
        snapshot = self.snapshot
        if publish_at and tid == "T04":
            snapshot = replace(snapshot, publish_at=now - timedelta(minutes=1))
        verdict = decide(TRANSITIONS[tid], snapshot, who, now, note_given=note)
        if verdict.outcome != "ok":
            return
        self.snapshot = snapshot
        if TRANSITIONS[tid].target.value in PUBLISHED:
            assert has_image(self.snapshot)
        self._apply(tid, who)

    @rule(role=st.sampled_from(ROLES), revert=st.booleans(), same_actor=st.booleans())
    def change_content(self, role: str, revert: bool, same_actor: bool) -> None:
        """A field write or a revert: both go through the same plan, revert also by state."""
        who = actor(role, sub="x" if same_actor else "y")
        if revert and self.snapshot.state not in REVERTIBLE:
            return
        self.counter += 1
        plan = plan_patch(self.snapshot, who, {"title": f"Titel {self.counter}"})
        if not plan.locked:
            self.snapshot = replace(self.snapshot, **plan.changes, rev=self.snapshot.rev + 1)

    @rule(late=st.sampled_from([0, 1, 13, 31, 60]))
    def worker(self, late: int) -> None:
        now = self.now + timedelta(days=late) + timedelta(hours=1)
        snapshot = self.snapshot
        row = AdvanceRow(
            snapshot.state,
            snapshot.publish_at,
            snapshot.ends_at,
            snapshot.origin_kind,
            now - timedelta(days=late),
        )
        tid = due_transition(row, now)
        if tid is None:
            return
        assert tid in SYSTEM_TRANSITIONS
        system = actor("system")
        verdict = decide(TRANSITIONS[tid], snapshot, system, now)
        if verdict.outcome == "ok":
            if TRANSITIONS[tid].target.value in PUBLISHED:
                assert has_image(snapshot) and snapshot.approved_by
                assert not snapshot.approved_by.startswith("system:")
            self._apply(tid, system)

    @rule(name=st.sampled_from(sorted(PUBLIC_TO)))
    def public_action(self, name: str) -> None:
        target = next_public_status(self.snapshot.state, self.snapshot.public_status, name)
        if target is not None:
            self.snapshot = replace(self.snapshot, public_status=target)

    @rule()
    def three_paths_agree_on_the_image(self) -> None:
        snapshot = replace(self.snapshot, state="approved", approved_by="person", publish_at=NOW)
        human = decide(TRANSITIONS["T05"], snapshot, actor("editor", "e"), NOW)
        system = decide(TRANSITIONS["T05"], snapshot, actor("system"), NOW)
        image_missing = not has_image_file(snapshot)
        assert ("image_required" in [r.code for r in human.reasons]) is image_missing
        assert ("image_required" in [r.code for r in system.reasons]) is image_missing

    @invariant()
    def a_published_state_has_a_reason_to_be(self) -> None:
        if self.snapshot.state in PUBLISHED:
            assert has_image(self.snapshot)

    @invariant()
    def approved_content_only_changes_through_t06(self) -> None:
        if self.snapshot.state == "approved":
            assert self.snapshot.title == self.title_at_approval

    @invariant()
    def live_has_a_human_approval(self) -> None:
        if self.snapshot.state == "live":
            assert self.snapshot.approved_by is not None
            assert not self.snapshot.approved_by.startswith("system:")

    @invariant()
    def public_status_needs_live_or_later(self) -> None:
        if self.snapshot.state not in {"live", "followup", "archived"}:
            assert self.snapshot.public_status == "scheduled"


TestPipelineMachine = PipelineMachine.TestCase
TestPipelineMachine.settings = settings(max_examples=200, stateful_step_count=30, deadline=None)
