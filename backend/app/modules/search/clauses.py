"""SQL fragments of the search: the match and rank of one word, the visibility of documents.

Every fragment is a string that only contains column names, constants and `:pN` placeholders
made by `Params.bind`; user input never becomes part of the text. The thresholds follow the
measurements of contract 6.2: a typed word matches a title at a word similarity of 0.5 or
more, and a title word of five or more letters matches a longer typed word (compounds) at
more than 0.6.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Uuid
from sqlalchemy.dialects.postgresql import ARRAY

from app.modules.search.filters import Reader
from app.modules.search.params import Params
from app.modules.search.words import Word

CFG = "'de_unaccent'::regconfig"
FORWARD_THRESHOLD = 0.5
REVERSE_THRESHOLD = 0.6
REVERSE_MIN_LETTERS = 5
TRIGRAM_FACTOR = 0.5
TITLE_BONUS = 1.0
DOCUMENT_FACTOR = 0.1
NAME_FACTOR = 0.5


@dataclass(frozen=True, slots=True)
class WordSql:
    """The SQL pieces of one word: its tsquery, its folded text and whether it may be fuzzy."""

    tsquery: str
    folded: str
    fuzzy: bool


def uuid_array(params: Params, ids: frozenset) -> str:
    """Bind a set of ids as a `uuid[]` and return the placeholder."""
    return params.bind(sorted(ids, key=str), ARRAY(Uuid))


def word_sql(params: Params, word: Word) -> WordSql:
    """Bind a word and build its tsquery (typed and transliterated spelling) and folded text."""
    typed, folded = params.bind(word.text), params.bind(word.folded)
    return WordSql(
        f"(websearch_to_tsquery({CFG}, {typed}) || websearch_to_tsquery({CFG}, {folded}))",
        f"immutable_unaccent(lower({typed}))",
        word.fuzzy,
    )


def _reverse(word: WordSql, title: str) -> str:
    return (
        "coalesce((SELECT max(word_similarity(tw, "
        f"{word.folded})) FROM regexp_split_to_table({title}, '[^[:alnum:]]+') AS tw "
        f"WHERE length(tw) >= {REVERSE_MIN_LETTERS}), 0)"
    )


def trigram_match(word: WordSql, title: str) -> str:
    """The typo and compound test on a folded title (false for a word that may not be fuzzy)."""
    if not word.fuzzy:
        return "false"
    return (
        f"(word_similarity({word.folded}, {title}) >= {FORWARD_THRESHOLD}"
        f" OR {_reverse(word, title)} > {REVERSE_THRESHOLD})"
    )


def trigram_rank(word: WordSql, title: str) -> str:
    """The similarity of a word to a title, 0 for a word that may not be fuzzy."""
    if not word.fuzzy:
        return "0"
    return f"greatest(word_similarity({word.folded}, {title}), {_reverse(word, title)})"


def word_match(word: WordSql, tsv: str, title: str, extra: str) -> str:
    """One word matches by full text, by trigram or by the scope's extra condition."""
    return f"({tsv} @@ {word.tsquery} OR {trigram_match(word, title)} OR {extra})"


def word_rank(word: WordSql, tsv: str, title: str, title_text: str, extra_rank: str) -> str:
    """The rank of one word: full text or half the trigram, the title bonus, the extras."""
    return (
        f"(CASE WHEN {tsv} @@ {word.tsquery} THEN ts_rank({tsv}, {word.tsquery})"
        f" ELSE {TRIGRAM_FACTOR} * {trigram_rank(word, title)} END"
        f" + CASE WHEN to_tsvector({CFG}, {title_text}) @@ {word.tsquery}"
        f" THEN {TITLE_BONUS} ELSE 0 END + {extra_rank})"
    )


def document_visible(reader: Reader, params: Params, own: str, org: str) -> str:
    """The condition under which a document `d` is readable.

    An own dossier shows `org` and `shared` documents, `team` only in organizations with
    team access; a foreign (archived) dossier shows `shared` documents only. `own` and
    `org` are SQL expressions for the dossier of the document.
    """
    team = (
        "true"
        if reader.team_orgs is None
        else f"{org} = ANY({uuid_array(params, reader.team_orgs)})"
    )
    return (
        f"(({own} AND (d.visibility IN ('org', 'shared')"
        f" OR (d.visibility = 'team' AND {team})))"
        f" OR (NOT ({own}) AND d.visibility = 'shared'))"
    )
