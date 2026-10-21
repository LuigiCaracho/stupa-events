"""Canary data (E39, E41): every non-public place carries its own `CANARY-INTERNAL-<FIELD>`.

`seed_canary` builds dossiers whose public parts carry `CANARY-PUBLIC-*` strings (the proof
that a scan finds public text at all) and whose internal parts (files, documents, comments,
quotes, notes, outcome, facts, people, private addresses, drafts) carry a unique internal
string. The tests then read every public and every foreign-facing response as raw bytes
and look for `CANARY-INTERNAL-` and the digits of the secret amount.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from tests.integration.archive.fixture import archived_movienight
from tests.integration.events.harness import Api, future

INTERNAL = "CANARY-INTERNAL-"
FORMAT_ONLY = "LIBRARYONLY-"
PUBLIC_TITLE = "CANARY-PUBLIC-TITLE"
PUBLIC_SUMMARY = "CANARY-PUBLIC-SUMMARY"
AMOUNT_DIGITS = "98765432101"


def format_mark(name: str) -> str:
    """Return the canary string of a format field: shared with the library, never public."""
    return f"{FORMAT_ONLY}{name}"


def mark(name: str) -> str:
    """Return the canary string of a field."""
    return f"{INTERNAL}{name}"


@dataclass
class Canary:
    """The ids of the canary dossiers."""

    published: str
    archived: str
    hidden_text: str
    private_venue: str
    hidden_venue: str
    drafts: list[str] = field(default_factory=list)


async def internal_bits(api: Api, eid: str) -> None:
    """Hang the internal strings onto a dossier (rows written directly, as a hostile import would)."""
    sql = api.sql
    await sql(
        "UPDATE event SET created_by = :c, outcome = CAST(:o AS jsonb), "
        "facts = CAST(:f AS jsonb) WHERE id = :e",
        c=f"sub-{mark('SUBCREATOR')}",
        o=json.dumps(
            {
                "attendance": 5,
                "costsCents": int(AMOUNT_DIGITS),
                "notes": mark("OUTCOMENOTES"),
                "waived": False,
                "waivedReason": mark("OUTCOMENOTES"),
            }
        ),
        f=json.dumps({"noisePermitRef": mark("FACTS")}),
        e=eid,
    )
    for kind, visibility, scan, name, extra in (
        ("other", "team", "clean", "TEAMFILE", {}),
        ("other", "org", "clean", "ORGFILE", {"alt": "ALTTEXT", "credit": "CREDITSOURCE"}),
        ("other", "shared", "pending", "SHAREDPENDING", {}),
        ("other", "shared", "infected", "SHAREDINFECTED", {}),
        ("business_plan", "org", "clean", "BUSINESSPLAN", {}),
        ("contract", "org", "clean", "CONTRACT", {}),
    ):
        await sql(
            "INSERT INTO attachment (event_id, kind, display_name, storage_name, mime, size_bytes, "
            "sha256, scan_status, visibility, alt_text, credit, source_url) VALUES (:e, :k, :n, 'x', "
            "'application/pdf', 1, :h, :s, :v, :alt, :credit, :src)",
            e=eid,
            k=kind,
            n=mark(name),
            h=f"{name:0<64}"[:64],
            s=scan,
            v=visibility,
            alt=mark(extra["alt"]) if extra else None,
            credit=mark(extra["credit"]) if extra else None,
            src=f"https://{mark('CREDITSOURCE').lower()}.example" if extra else None,
        )
    for kind, visibility, name in (
        ("notes", "team", "DOCTEAM"),
        ("notes", "org", "DOCORG"),
        ("notes", "org", "NOTE"),
        ("mail_template", "org", "MAILTPL"),
    ):
        await sql(
            "INSERT INTO document (event_id, kind, title, body_md, visibility) "
            "VALUES (:e, :k, :t, :b, :v)",
            e=eid,
            k=kind,
            t=mark(name),
            b=mark(name),
            v=visibility,
        )
    await sql(
        "INSERT INTO document (event_id, kind, title, body_md, visibility) "
        "SELECT :e, 'retrospective', :t, :t, 'org' WHERE NOT EXISTS "
        "(SELECT 1 FROM document WHERE event_id = :e AND kind = 'retrospective')",
        e=eid,
        t=mark("RETRO"),
    )
    await sql(
        "INSERT INTO comment (event_id, author_sub, body_md) VALUES (:e, 'sub-editor', :b)",
        e=eid,
        b=mark("COMMENT"),
    )
    await sql(
        "INSERT INTO comment (event_id, author_sub, body_md, parent_id) "
        "SELECT :e, 'sub-editor', :b, id FROM comment WHERE event_id = :e AND body_md = :p",
        e=eid,
        b=mark("REPLY"),
        p=mark("COMMENT"),
    )
    await sql(
        "INSERT INTO quote (event_id, grp, vendor, amount_cents, note) VALUES (:e, 'Technik', :v, :a, :n)",
        e=eid,
        v=mark("QUOTEVENDOR"),
        a=int(AMOUNT_DIGITS),
        n=mark("QUOTENOTE"),
    )
    await sql(
        "INSERT INTO checklist_item (event_id, position, text, phase, waived_reason) "
        "VALUES (:e, 'q', :t, 'live', :w)",
        e=eid,
        t=mark("CHECKLIST"),
        w=mark("WAIVED"),
    )
    await sql(
        "INSERT INTO notification (recipient_sub, kind, event_id, params, link) "
        "VALUES ('sub-org-fsi', 'comment_added', :e, CAST(:p AS jsonb), '/x')",
        e=eid,
        p=json.dumps({"note": mark("NOTIFPARAM")}),
    )
    await sql(
        "INSERT INTO event_status_event (event_id, from_state, to_state, transition_id, note) "
        "VALUES (:e, 'published', 'published', 'cancel', :n)",
        e=eid,
        n=mark("CANCELNOTE"),
    )
    await sql(
        "INSERT INTO event_revision (event_id, rev, snapshot, change_note) "
        "SELECT :e, 900, '{}'::jsonb, :n",
        e=eid,
        n=mark("REVNOTE"),
    )
    await sql(
        "UPDATE organization SET contact_public = CAST(:c AS jsonb) WHERE slug = 'fsi'",
        c=json.dumps({"email": f"{mark('CONTACT').lower()}@example.org"}),
    )


async def internal_format(api: Api, eid: str) -> None:
    """Give a dossier a format whose description, defaults and master howto are internal."""
    await api.sql(
        "INSERT INTO format (slug, title, organization_id, defaults, description_md, created_by) "
        "SELECT 'canary-format', 'Canary Format', id, CAST(:d AS jsonb), :m, 'sub-editor' "
        "FROM organization WHERE slug = 'fsi'",
        d=json.dumps({"notes": format_mark("FORMATDEFAULTS")}),
        m=format_mark("FORMATDESC"),
    )
    await api.sql(
        "INSERT INTO document (format_id, kind, title, body_md, visibility) "
        "SELECT id, 'howto', :t, :t, 'shared' FROM format WHERE slug = 'canary-format'",
        t=format_mark("MASTERHOWTO"),
    )
    await api.sql(
        "UPDATE format SET master_howto_document_id = "
        "(SELECT id FROM document WHERE format_id = format.id) WHERE slug = 'canary-format'"
    )
    await api.sql(
        "UPDATE event SET format_id = (SELECT id FROM format WHERE slug = 'canary-format'), "
        "location_confirmed_by = :c WHERE id = :e",
        c=f"sub-{mark('SUBCONFIRMER')}",
        e=eid,
    )


async def drop_canary_format(api: Api) -> None:
    """Remove the canary format and everything that points at it."""
    await api.sql(
        "UPDATE event SET format_id = NULL WHERE format_id IN "
        "(SELECT id FROM format WHERE slug = 'canary-format')"
    )
    await api.sql("UPDATE format SET master_howto_document_id = NULL WHERE slug = 'canary-format'")
    await api.sql(
        "DELETE FROM document WHERE format_id IN (SELECT id FROM format WHERE slug = 'canary-format')"
    )
    await api.sql("DELETE FROM format WHERE slug = 'canary-format'")


async def seed_canary(api: Api) -> Canary:
    """Build the canary dossiers and return their ids."""
    published = await api.to_state(
        "published",
        title=PUBLIC_TITLE,
        summary=PUBLIC_SUMMARY,
        venueText="CANARY-PUBLIC-VENUE",
        descriptionMd="CANARY-PUBLIC-DESCRIPTION",
    )
    await internal_bits(api, published["id"])
    await internal_format(api, published["id"])
    archived = await archived_movienight(api, title="CANARY-PUBLIC-ARCHIVED")
    await internal_bits(api, archived)
    await api.sql(
        "INSERT INTO document (event_id, kind, title, body_md, visibility) "
        "VALUES (:e, 'notes', 'CANARY-PUBLIC-SHARED', 'CANARY-PUBLIC-SHARED', 'shared')",
        e=archived,
    )
    hidden_text = await api.to_state(
        "published",
        title="Ort ohne Bestätigung",
        venueText=mark("UNCONFIRMEDTEXT"),
        startsAt=future(20).isoformat(),
        endsAt=future(20, 2).isoformat(),
    )
    await api.sql(
        "UPDATE event SET location_precision = 'hidden', location_confirmed_at = NULL WHERE id = :e",
        e=hidden_text["id"],
    )
    await api.sql(
        "INSERT INTO venue (slug, name, address, postcode, city, notes, public_precision, is_private)"
        " VALUES ('canary-private', 'Bei Ada', :a, :p, 'Reutlingen', :n, 'exact', true),"
        " ('canary-hidden', 'Saal Hidden', :h, '72762', 'Reutlingen', NULL, 'hidden', false)",
        a=mark("PRIVATEADDRESS"),
        p=mark("PRIVATEADDRESS"),
        n=mark("PRIVATEADDRESS"),
        h=mark("HIDDENADDRESS"),
    )
    private = await api.to_state(
        "published",
        title="Privater Ort",
        startsAt=future(21).isoformat(),
        endsAt=future(21, 2).isoformat(),
    )
    await api.sql(
        "UPDATE event SET venue_id = (SELECT id FROM venue WHERE slug = 'canary-private') WHERE id = :e",
        e=private["id"],
    )
    hidden = await api.to_state(
        "published",
        title="Versteckte Adresse",
        startsAt=future(22).isoformat(),
        endsAt=future(22, 2).isoformat(),
    )
    await api.sql(
        "UPDATE event SET venue_id = (SELECT id FROM venue WHERE slug = 'canary-hidden') WHERE id = :e",
        e=hidden["id"],
    )
    draft = await api.to_state("draft", title=mark("DRAFT"))
    unpublished = await api.to_state("published", title=mark("UNPUBLISHED"))
    assert (await api.act("organizer-fsi", unpublished["id"], "unpublish")).status_code == 200
    drafts = [draft["id"], unpublished["id"]]
    return Canary(published["id"], archived, hidden_text["id"], private["id"], hidden["id"], drafts)
