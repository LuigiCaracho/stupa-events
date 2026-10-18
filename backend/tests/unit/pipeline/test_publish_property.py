"""Property: no sequence of actions reaches `approved` or `live` without poster or exception.

The machine drives the pure `decide` function the way the service does (the state only
changes when the verdict is `ok`) and mutates the poster and the exception in arbitrary
order. The database trigger covers the same rule below the service (integration suite).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from app.modules.pipeline.snapshot import PosterSnapshot
from app.modules.pipeline.transitions import TRANSITIONS, decide
from tests.unit.pipeline.support import NOW, actor, snap

ROLES = ["submitter", "organizer", "approver", "editor"]
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


class PipelineMachine(RuleBasedStateMachine):
    """A dossier moved by random actors while its poster changes at random."""

    def __init__(self) -> None:
        super().__init__()
        self.snapshot = snap(state="idea", poster=None)

    @rule(poster=POSTERS)
    def set_poster(self, poster: PosterSnapshot | None) -> None:
        if self.snapshot.state in {"idea", "planning", "in_review"}:
            self.snapshot = replace(self.snapshot, poster=poster)

    @rule(reason=st.sampled_from([None, "short", "Hochschulveranstaltung ohne Motiv"]))
    def grant_exception(self, reason: str | None) -> None:
        if reason and len(reason) >= 10:
            self.snapshot = replace(self.snapshot, image_exception_reason=reason)

    @rule(tid=st.sampled_from(sorted(TRANSITIONS)), role=st.sampled_from(ROLES), late=st.booleans())
    def fire(self, tid: str, role: str, late: bool) -> None:
        now = NOW + (timedelta(days=30) if late else timedelta(0))
        transition = TRANSITIONS[tid]
        verdict = decide(transition, self.snapshot, actor(role, sub="x"), now)
        if verdict.outcome != "ok":
            return
        if transition.target.value in {"approved", "live"}:
            poster = self.snapshot.poster
            assert (poster is not None and poster.usable) or self.snapshot.image_exception_reason
        self.snapshot = replace(self.snapshot, state=transition.target.value)

    @invariant()
    def a_published_state_has_a_reason_to_be(self) -> None:
        if self.snapshot.state in {"approved", "live"}:
            assert self.snapshot.poster is not None or self.snapshot.image_exception_reason


TestPipelineMachine = PipelineMachine.TestCase
TestPipelineMachine.settings = settings(max_examples=200, stateful_step_count=30, deadline=None)
