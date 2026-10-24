"""Pure target-state rules: wanted lists, list names and the opt-out-wins plan."""

from __future__ import annotations

from app.modules.subscriptions.listmonk_port import ListmonkSubscriber
from app.modules.subscriptions.listmonk_sync import ALL_KEY, Plan, desired_keys, list_name, plan


def sub(status: str = "enabled", **lists: str) -> ListmonkSubscriber:
    return ListmonkSubscriber(
        1, "a@example.test", status, {int(k[1:]): v for k, v in lists.items()}
    )


def test_only_parties_no_meetings_maps_to_party_lists() -> None:
    assert desired_keys(True, ["party", "campusfest"]) == {ALL_KEY, "party", "campusfest"}


def test_no_mail_wants_no_list() -> None:
    assert desired_keys(False, ["party"]) == set()


def test_list_names_carry_the_events_prefix() -> None:
    assert list_name("party") == "events-party"
    assert list_name(ALL_KEY) == "events-alle"


def test_new_subscriber_gets_the_wanted_lists() -> None:
    assert plan(None, {1, 2}) == Plan("sync", frozenset({1, 2}))


def test_blocklisted_subscriber_is_an_opt_out() -> None:
    assert plan(sub("blocklisted", l1="unsubscribed"), {1}).action == "opted_out"


def test_unsubscribed_from_every_wanted_list_is_an_opt_out() -> None:
    assert plan(sub(l1="unsubscribed", l2="unsubscribed"), {1, 2}).action == "opted_out"


def test_a_left_list_is_not_added_again() -> None:
    assert plan(sub(l1="confirmed", l2="unsubscribed"), {1, 2}) == Plan("sync", frozenset({1}))


def test_nothing_wanted_means_leave_all_lists() -> None:
    assert plan(sub(l1="confirmed"), set()) == Plan("sync", frozenset())
