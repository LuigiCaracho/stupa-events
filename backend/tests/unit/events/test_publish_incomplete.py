"""Only the title, the start and the organization stop a publication."""

from __future__ import annotations

import pytest

from app.modules.events.publish import missing_fields, require_complete
from app.shared.errors import ValidationProblem
from tests.unit.events.test_access_and_revisions import event


def test_a_dossier_with_the_three_fields_is_complete_without_anything_else() -> None:
    bare = event(
        summary=None,
        venue_text=None,
        primary_category_id=None,
        hero_attachment_id=None,
    )
    assert missing_fields(bare) == []
    require_complete(bare)


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"title": " "}, "title"),
        ({"starts_at": None}, "startsAt"),
        ({"organization_id": None}, "organizationId"),
    ],
)
def test_each_missing_field_is_named(change: dict, field: str) -> None:
    broken = event(**change)
    assert missing_fields(broken) == [field]
    with pytest.raises(ValidationProblem) as caught:
        require_complete(broken)
    assert caught.value.code == "publish_incomplete"
    assert caught.value.extensions == {"reasons": [{"field": field}]}
    assert [e.field for e in caught.value.errors or []] == [field]


def test_all_missing_fields_come_together() -> None:
    broken = event(title="", starts_at=None, organization_id=None)
    assert missing_fields(broken) == ["title", "startsAt", "organizationId"]


def test_clean_reason_strips_empties_and_caps() -> None:
    import pytest

    from app.modules.events.step import MAX_REASON, clean_reason
    from app.shared.errors import ValidationProblem

    assert clean_reason("  Saal weg ") == "Saal weg"
    assert clean_reason("   ") is None and clean_reason(None) is None
    with pytest.raises(ValidationProblem):
        clean_reason("x" * (MAX_REASON + 1))
