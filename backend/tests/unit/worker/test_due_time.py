"""Local date logic of the due reminder cron."""

from __future__ import annotations

from datetime import UTC, date, datetime

from worker.mail import tomorrow_local


def test_tomorrow_uses_berlin_date_not_utc() -> None:
    assert tomorrow_local(datetime(2026, 7, 1, 22, 30, tzinfo=UTC)) == date(2026, 7, 3)
    assert tomorrow_local(datetime(2026, 7, 1, 10, 10, tzinfo=UTC)) == date(2026, 7, 2)


def test_dst_change_day() -> None:
    assert tomorrow_local(datetime(2026, 10, 24, 12, 10, tzinfo=UTC)) == date(2026, 10, 25)
    assert tomorrow_local(datetime(2026, 10, 25, 12, 10, tzinfo=UTC)) == date(2026, 10, 26)


async def test_reminders_are_skipped_without_a_queue() -> None:
    from worker.mail import send_due_reminders

    assert "skipped" in await send_due_reminders({"redis": None})
