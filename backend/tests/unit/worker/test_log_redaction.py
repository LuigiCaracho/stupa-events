"""The worker log names the job but never its arguments."""

from __future__ import annotations

import logging

import pytest
from arq.utils import args_to_string

import worker.main  # noqa: F401  (installs the filter)


def test_job_start_line_keeps_the_function_but_drops_the_mail(
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload = {"to": ["ada@example.org"], "text": "https://x/bestaetigen/SECRETTOKEN"}
    with caplog.at_level(logging.INFO, logger="arq.worker"):
        logging.getLogger("arq.worker").info(
            "%6.2fs → %s(%s)%s", 0.25, "mail:abc:send_mail", args_to_string([payload], {}), ""
        )
    text = caplog.text
    assert "mail:abc:send_mail(…)" in text
    assert "ada@example.org" not in text and "SECRETTOKEN" not in text


def test_other_lines_pass_unchanged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="arq.worker"):
        logging.getLogger("arq.worker").info("%s ● %s", "cron:outbox_run", "done=1")
    assert "cron:outbox_run ● done=1" in caplog.text
