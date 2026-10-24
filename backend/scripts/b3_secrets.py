"""B3 acceptance, item i: tokens only as hashes in the DB, no token and no address in any log.

Every token and address the run handled is searched in a dump of the subscription tables, in
the journals of API, worker and `ng serve`, in the logs of Postgres and of a throwaway nginx with
the production config (fed with token paths and a confirm POST), and in Redis outside the arq
mail jobs, which carry the mail body by design. The SHA-256 of the calendar tokens must be in the
dump instead.
"""

from __future__ import annotations

import hashlib
import time

import httpx

from scripts import b3_ops as ops
from scripts.acceptance_common import check, step
from scripts.b3_flow import Seen


def _hits(text: str, needles: set[str]) -> set[str]:
    lowered = text.lower()
    return {n for n in needles if n.lower() in lowered}


def _local_parts(addresses: set[str]) -> set[str]:
    return {a.split("@")[0] for a in addresses}


def feed_nginx(seen: Seen) -> str:
    """Send token requests through the production nginx config; return its log."""
    base = ops.nginx_up()
    try:
        for _ in range(30):
            try:
                httpx.get(f"{base}/healthz", timeout=2)
                break
            except httpx.HTTPError:
                time.sleep(1)
        codes: dict[str, set[int]] = {}
        for token in sorted(seen.tokens):
            for path in (f"/ics/p/{token}.ics", f"/abo/{token}", f"/bestaetigen/{token}"):
                kind = path.split("/")[1]
                codes.setdefault(kind, set()).add(
                    httpx.get(f"{base}{path}", timeout=10).status_code
                )
                time.sleep(0.25)
        confirm = httpx.post(
            f"{base}/api/public/subscriptions/confirm", json={"token": max(seen.tokens)}, timeout=10
        )
        codes["confirm"] = {confirm.status_code}
        time.sleep(1)
        step(f"i: nginx answered {codes}")
        check(codes["abo"] == codes["bestaetigen"] == {200}, "i: nginx serves the token pages")
        check(200 in codes["ics"] and 404 in codes["ics"], "i: live and dead calendar tokens")
        return ops.nginx_log()
    finally:
        ops.nginx_down()


def check_secrets(seen: Seen, since: str) -> dict[str, int]:
    """Item i: hashes only in the DB, nothing secret in the logs."""
    dump = ops.dump_subscription_tables()
    tokens, addresses = seen.tokens, seen.addresses
    check(not _hits(dump, tokens), f"i: none of {len(tokens)} tokens is in the subscription tables")
    check(not _hits(dump, addresses), f"i: none of {len(addresses)} addresses is stored in clear")
    hashed = {hashlib.sha256(t.encode()).hexdigest() for t in tokens}
    check(bool(_hits(dump, hashed)), "i: the tables hold SHA-256 hashes of the live tokens")
    logs = ops.unit_logs(since)
    logs["postgres"] = ops.container_log(ops.POSTGRES, since)
    logs["listmonk"] = ops.container_log(ops.LISTMONK, since)
    logs["nginx"] = feed_nginx(seen)
    needles = tokens | addresses | _local_parts(addresses)
    sizes = {}
    for name, text in logs.items():
        sizes[name] = len(text.splitlines())
        hits = _hits(text, tokens | (set() if name == "listmonk" else needles))
        check(not hits, f"i: {name} log ({sizes[name]} lines) names no token or address")
    check(sizes["nginx"] >= 3 * len(tokens), f"i: nginx logged {sizes['nginx']} lines")
    check(sizes["stupa-worker"] > 0 and sizes["listmonk"] > 0, "i: worker and Listmonk logged")
    outside = ops.redis_dump()
    check(not _hits(outside, tokens), "i: no token in Redis outside the mail jobs")
    check(not _hits(outside, addresses), "i: no address in Redis outside the mail jobs")
    return sizes
