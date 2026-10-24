"""Interests to categories: single, several, faculty, children, errors, the cap."""

from __future__ import annotations

import pytest

from app.modules.subscriptions import interests
from app.modules.subscriptions.interests import (
    NoInterestError,
    TooManyCategoriesError,
    UnknownInterestError,
    resolve_categories,
)
from tests.unit.subscriptions.catalog import build_catalog

CATALOG = build_catalog()


def test_only_parties_and_no_meetings_gives_the_party_categories_and_no_meeting() -> None:
    result = resolve_categories(CATALOG, ["party"], False, None)
    assert result.interests == ("party",)
    assert result.categories == ("party", "campusfest", "festival", "get-together")
    assert "sitzung" not in result.categories


def test_several_interests_keep_their_order_and_drop_duplicates() -> None:
    result = resolve_categories(CATALOG, ["kultur", "party", "kultur"], False, None)
    assert result.interests == ("kultur", "party")
    assert result.categories[:2] == ("kino", "konzert")
    assert len(result.categories) == len(set(result.categories))


def test_the_meetings_answer_adds_the_meetings_interest() -> None:
    result = resolve_categories(CATALOG, ["party"], True, None)
    assert result.interests == ("party", "sitzung")
    assert "sitzung" in result.categories


def test_the_faculty_answer_adds_the_faculty_category_but_not_its_parent() -> None:
    result = resolve_categories(CATALOG, ["party"], False, "fachschaft:informatik-fsi")
    assert "fachschaft-informatik-fsi" in result.categories
    assert "fachschaft" not in result.categories
    assert "fachschaft-technik-tec" not in result.categories
    assert result.interests[-1] == "fachschaft:informatik-fsi"


def test_esb_stuco_keeps_its_slug_as_the_faculty_value() -> None:
    assert "fachschaft:esb-stuco" in CATALOG.faculties()
    assert resolve_categories(CATALOG, [], False, "fachschaft:esb-stuco").categories == (
        "esb-stuco",
    )


def test_a_faculty_value_is_also_accepted_inside_the_interest_list() -> None:
    result = resolve_categories(CATALOG, ["fachschaft:technik-tec"], False, None)
    assert result.categories == ("fachschaft-technik-tec",)


def test_the_parent_of_a_chosen_category_brings_its_children() -> None:
    parent_catalog = interests.Catalog(
        interests={"x": interests.InterestInfo("x", "X", ("fachschaft",))},
        categories=CATALOG.categories,
    )
    result = resolve_categories(parent_catalog, ["x"], False, None)
    assert result.categories[0] == "fachschaft"
    assert {"fachschaft-informatik-fsi", "fachschaft-technik-tec", "esb-stuco"} <= set(
        result.categories
    )


def test_an_unknown_interest_is_refused() -> None:
    with pytest.raises(UnknownInterestError):
        resolve_categories(CATALOG, ["party", "nonsense"], False, None)
    with pytest.raises(UnknownInterestError):
        resolve_categories(CATALOG, ["party"], False, "fachschaft:nope")


def test_nothing_chosen_is_refused() -> None:
    with pytest.raises(NoInterestError):
        resolve_categories(CATALOG, [], False, None)


def test_an_interest_whose_categories_are_all_inactive_gives_nothing() -> None:
    catalog = build_catalog(without=frozenset({"party", "campusfest", "festival", "get-together"}))
    with pytest.raises(NoInterestError):
        resolve_categories(catalog, ["party"], False, None)
    assert resolve_categories(catalog, ["party", "kultur"], False, None).categories == (
        "kino",
        "konzert",
    )


def test_more_than_forty_categories_are_refused() -> None:
    wide = {f"c{i}": interests.CategoryInfo(f"c{i}", f"C{i}", "format", None) for i in range(41)}
    catalog = interests.Catalog({"all": interests.InterestInfo("all", "All", tuple(wide))}, wide)
    with pytest.raises(TooManyCategoriesError):
        resolve_categories(catalog, ["all"], False, None)


def test_faculty_values_and_labels() -> None:
    assert interests.faculty_value("fachschaft-informatik-fsi") == "fachschaft:informatik-fsi"
    assert interests.faculty_value("esb-stuco") == "fachschaft:esb-stuco"
    assert CATALOG.label("party") == "Partys und Feiern"
    assert CATALOG.label("fachschaft:informatik-fsi") == "Fachschaft Informatik"
