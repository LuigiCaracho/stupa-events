"""The Listmonk jobs skip themselves while their configuration is missing."""

from __future__ import annotations

import pytest

from tests._support.factories import make_settings
from worker.digest import build_digest_drafts
from worker.outbox import outbox_run
from worker.privacy import purge_expired
from worker.reconcile import reconcile_listmonk

JOBS = [outbox_run, reconcile_listmonk, build_digest_drafts, purge_expired]


@pytest.mark.parametrize("job", JOBS)
async def test_job_skips_without_configuration(job) -> None:  # noqa: ANN001
    assert (await job({"settings": make_settings()})).endswith("skipped (not configured)")


async def test_purge_needs_no_listmonk_but_the_subs_database_and_key() -> None:
    ctx = {"settings": make_settings(pgcrypto_email_key="k" * 32)}
    assert (await purge_expired(ctx)).endswith("skipped (not configured)")


def test_cron_registration_matches_the_contract() -> None:
    from worker.main import WorkerSettings

    jobs = {c.name.removeprefix("cron:"): c for c in WorkerSettings.cron_jobs}
    assert jobs["outbox_run"].minute is None and jobs["outbox_run"].unique
    assert (jobs["reconcile_listmonk"].hour, jobs["reconcile_listmonk"].minute) == (3, 10)
    assert (jobs["purge_expired"].hour, jobs["purge_expired"].minute) == (3, 20)
    digest = jobs["build_digest_drafts"]
    assert (digest.weekday, digest.hour, digest.minute) == (0, 5, 0)
    assert all(
        jobs[n].unique for n in ("reconcile_listmonk", "purge_expired", "build_digest_drafts")
    )
