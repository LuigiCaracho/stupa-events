"""Operations of the B3 acceptance outside the public API: SQL, Redis, containers, logs.

SQL runs as the Postgres superuser inside the dev container, because the subscription tables
belong to the role `events_subs` alone and the app role cannot read them; it only reads or moves
clocks. Redis loses the hourly subscription counters between the timing rounds, so the limit of
ten sign-ups per IP and hour does not end the measurement. The Listmonk container is stopped and
started for the outage check; nothing else of the stack is touched.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

POSTGRES = "stupa-events-dev-postgres-1"
REDIS = "stupa-events-dev-redis-1"
LISTMONK = "stupa-events-dev-listmonk-1"
UNITS = ("stupa-api", "stupa-worker", "stupa-ng")
NGINX = "b3-acceptance-nginx"
NGINX_PORT = 8082
WEB = Path(__file__).resolve().parents[2] / "deploy" / "web"
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist" / "stupa-events" / "browser"


def _run(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def sql(statement: str) -> list[list[str]]:
    """Run one statement as superuser and return the rows as lists of text."""
    out = _run(
        "docker",
        "exec",
        POSTGRES,
        "psql",
        "-U",
        "postgres",
        "-d",
        "events",
        "-v",
        "ON_ERROR_STOP=1",
        "-AtF",
        "\t",
        "-c",
        statement,
    )
    return [line.split("\t") for line in out.splitlines() if line]


def value(statement: str) -> str:
    """Return the first column of the first row, or an empty string."""
    rows = sql(statement)
    return rows[0][0] if rows and rows[0] else ""


def dump_subscription_tables() -> str:
    """Return every row of the subscription tables as text (for the token and address search)."""
    tables = ("subscriber", "subscription_profile", "outbox", "digest_run", "listmonk_list")
    return "\n".join(
        _run("docker", "exec", POSTGRES, "pg_dump", "-U", "postgres", "-a", "-t", t, "events")
        for t in tables
    )


def reset_subscription_limits() -> None:
    """Drop the IP and address counters of the subscription routes and the public write bucket."""
    for pattern in ("rl:subs:*", "rl:write:ip:*"):
        keys = _run("docker", "exec", REDIS, "redis-cli", "--scan", "--pattern", pattern).split()
        if keys:
            _run("docker", "exec", REDIS, "redis-cli", "DEL", *keys)


def redis_dump() -> str:
    """Return every Redis key with its value as text, except the arq jobs and their results.

    A mail job carries the mail body with its link by design, so it is left out.
    """
    script = (
        'for k in $(redis-cli --scan); do case "$k" in arq:job:*|arq:result:*) continue;; esac; '
        't=$(redis-cli type "$k"); echo "$k"; '
        'case "$t" in string) redis-cli get "$k";; hash) redis-cli hgetall "$k";; '
        'list) redis-cli lrange "$k" 0 -1;; zset) redis-cli zrange "$k" 0 -1;; '
        'set) redis-cli smembers "$k";; esac; done'
    )
    return _run("docker", "exec", REDIS, "sh", "-c", script)


def listmonk_stop() -> None:
    """Stop the Listmonk container."""
    _run("docker", "stop", LISTMONK)


def listmonk_start() -> None:
    """Start the Listmonk container again."""
    _run("docker", "start", LISTMONK)


def unit_logs(since: str) -> dict[str, str]:
    """Return the journals of API, worker and `ng serve` since `since`."""
    return {
        unit: _run("journalctl", "--user", "-u", unit, "--since", since, "--no-pager", "-o", "cat")
        for unit in UNITS
    }


def container_log(name: str, since: str) -> str:
    """Return the log of a container since `since` (journalctl syntax).

    Docker on the dev laptop logs to journald, where `docker logs` answers nothing.
    """
    return _run("journalctl", f"CONTAINER_NAME={name}", "--since", since, "--no-pager", "-o", "cat")


def nginx_up() -> str:
    """Run the production nginx config in front of the host API; return its base URL.

    The container shares the host network so that `api:8000` (an extra hosts entry) reaches the
    uvicorn of the dev unit; only the listen port moves to 8082. The SPA is the local build.
    """
    nginx_down()
    conf = Path(tempfile.mkdtemp(prefix="b3-nginx-")) / "default.conf"
    conf.write_text((WEB / "nginx.conf").read_text().replace("listen 80;", f"listen {NGINX_PORT};"))
    mounts = [
        f"{conf}:/etc/nginx/conf.d/default.conf:ro",
        f"{DIST}:/usr/share/nginx/html:ro",
        f"{WEB / 'real-ip.conf.template'}:/etc/nginx/templates/real-ip.conf.template:ro",
        *(
            f"{WEB / name}:/etc/nginx/snippets/{name}:ro"
            for name in ("security-headers.conf", "api-proxy.conf", "proxy-cache.conf")
        ),
    ]
    _run(
        "docker",
        "run",
        "-d",
        "--name",
        NGINX,
        "--network",
        "host",
        "--add-host",
        "api:127.0.0.1",
        "-e",
        "TRUSTED_PROXY_IP=192.0.2.1",
        *(arg for m in mounts for arg in ("-v", m)),
        "nginx:1.27-alpine",
    )
    return f"http://127.0.0.1:{NGINX_PORT}"


def nginx_log() -> str:
    """Return the access and error log of the acceptance nginx."""
    return container_log(NGINX, "-1h")


def nginx_down() -> None:
    """Remove the acceptance nginx."""
    subprocess.run(["docker", "rm", "-f", NGINX], capture_output=True, check=False)
