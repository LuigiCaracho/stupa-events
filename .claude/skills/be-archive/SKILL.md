---
name: be-archive
description: Archive, formats, clone, follow-up, library and internal search of STUPA Events (M5). Neu aus Vorlage with the carry-over table, "Letztes Mal", formats with a master howto, "So lief es" (outcome, retrospective, verify-howto; voluntary since M5b), the library view, FTS plus trigram search with the right filter in SQL, the internal calendar. Use when working on clone, templates, formats, outcome, library or search.
---

# Archive and "So lief es": `app/modules/{archive,formats,followup,library,search}`, `events/{calendar,facts,location,allday}.py`

**Does:** Turns archived dossiers into templates (`POST /events/{id}/clone`), shows what happened last time, keeps
formats (Movienight) with a master howto, holds the voluntary "So lief es" section and finds everything again.
Contract: `docs/M5-KONTRAKT.md` (on top of M1 to M4).

## Key files

| File | Role |
|---|---|
| `archive/access.py` | `load_archive_readable` (own: any state, foreign: `archived` only; templates in `clonable.py`: own `published`/`archived`, foreign `archived`), `foreign_archived`; `load_visible` stays strict |
| `archive/carry_over.py` | `CARRY_OVER` table (one rule per part, own vs foreign), `plan` report, `reset_facts`; read by preview, clone and the UI |
| `archive/clone.py` | `clone_event` (one transaction), `preview_clone`, `source_parts`, `target_organization`, `clone_times`, `offset_of` |
| `archive/last_time.py` | `panel`: attendance always, costs/revenue/notes and a non-shared retrospective for the own organization only |
| `archive/templates.py`, `read.py`, `router.py` | template list on the search query, `GET /archive/{id}`, routes |
| `formats/service.py` | create, patch, verify, `save_as_format`, `set_event_format`, `new_edition`; `queries.py`, `howto.py`, `seed.py` |
| `followup/outcome.py`, `howto.py` | outcome write (If-Match, every state, the archive included), verify-howto (`published`, `archived`, `event.publish`; dates the format only with `verify_format`) |
| `library/service.py` | the list (documents by FTS+trigram, files by `ILIKE`), `adopt` (text only) |
| `search/query.py`, `clauses.py`, `words.py` | one builder per scope; `Params.bind` for every value; per-word FTS or trigram; the right filter first |
| `events/calendar.py`, `facts.py`, `location.py`, `allday.py` | `view=calendar`, facts profiles, `confirm-location`, all-day columns |

## Gotchas

- The right filter lives in SQL (`search/query.py` base queries): foreign dossiers only when `archived`, `team`
  documents only in organizations with `event.publish`/`dossier.read_restricted`, format documents only `shared`.
  Never filter after the query. `tests/integration/publicapi/test_canary.py` proves it with `CANARY-INTERNAL-*`.
- A foreign reader reaches `GET /archive/{id}`, `GET /documents/{id}` and attachment download/preview (`archive=True`),
  nothing else; every write on a foreign dossier stays 404/403.
- Clone makes a `draft` and never copies files, poster, quotes, comments, outcome, retrospective or links.
  `venue_text` is copied with `location_precision = hidden`; the feed shows it only after `confirm-location`.
- Search words: >= 3 letters may use the trigram (forward 0.5, title word >= 5 letters backwards 0.6); input with
  quotes, a leading `-` or `or` runs FTS only; `translit` adds the ae/oe/ue spelling. Highlights are segments cut at
  `chr(1)`/`chr(2)`, never HTML. 2 s statement timeout becomes 503 `search_timeout`.
- Test harness: `api.to_state("published")` creates a dossier and walks the lifecycle routes (`api.confirm_location` for a free venue text). The formats are
  re-seeded after every wipe (`clean_events`), because `TRUNCATE event CASCADE` also empties `format`.
- `tests/integration/archive/fixture.py: archived_movienight` builds a full archived edition through the real API.
