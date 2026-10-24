"""Keep job arguments out of the worker log.

arq logs every job start as `<ref>(<repr of the arguments>)`. A mail job's arguments are the
mail itself (recipient, subject, body with links and tokens), so the filter replaces them with
an ellipsis and keeps the timing, the job id and the function name. Installed once at import of
`worker.main`; arq's own logging config keeps existing loggers.
"""

from __future__ import annotations

import logging

_JOB_START = "%6.2fs → %s(%s)%s"


class JobArgsRedaction(logging.Filter):
    """Drop the argument text from arq's job start lines."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Rewrite the job start record; let every record through."""
        if record.msg == _JOB_START and isinstance(record.args, tuple) and len(record.args) == 4:
            waited, ref, _, extra = record.args
            record.args = (waited, ref, "…", extra)
        return True


def install() -> None:
    """Attach the filter to arq's worker logger (idempotent)."""
    target = logging.getLogger("arq.worker")
    if not any(isinstance(f, JobArgsRedaction) for f in target.filters):
        target.addFilter(JobArgsRedaction())
