"""Tiny dashboard that exposes every ``apibaseball`` method under ``/api/*``.

Standard-library port of the TypeScript Express example: it serves
``public/index.html`` and proxies each route to the SDK, so the API key never
reaches the browser.

Run with ``APIBASEBALL_KEY=... python examples/dashboard/server.py``.
"""

import json
import os
import re
import time
from collections.abc import Callable
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qs, urlsplit

from apibaseball import BaseballApiError, BaseballClient

PUBLIC_DIR = Path(__file__).parent / "public"

Query = dict[str, str]
Route = Callable[[BaseballClient, re.Match[str], Query], Any]


def num(value: str | None) -> int | None:
    """Parse an optional integer query value; empty or invalid means ``None``."""
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def items_per_page(value: str | None) -> int | Literal["*"] | None:
    return "*" if value == "*" else num(value)


ROUTES: list[tuple[re.Pattern[str], Route]] = [
    (re.compile(r"/api/countries"), lambda c, m, q: c.get_countries()),
    (
        re.compile(r"/api/leagues"),
        lambda c, m, q: c.get_leagues(
            page=num(q.get("page")),
            items_per_page=items_per_page(q.get("itemsPerPage")),
        ),
    ),
    (
        re.compile(r"/api/leagues/by-country/(\d+)"),
        lambda c, m, q: c.get_leagues_by_country(int(m[1])),
    ),
    (
        re.compile(r"/api/teams/by-league/(\d+)"),
        lambda c, m, q: c.get_teams_by_league(int(m[1])),
    ),
    (
        re.compile(r"/api/players"),
        lambda c, m, q: c.get_players(
            team_id=num(q.get("teamId")), league_id=num(q.get("leagueId"))
        ),
    ),
    (
        re.compile(r"/api/games"),
        lambda c, m, q: c.get_games(
            from_=q.get("from", ""),
            to=q.get("to", ""),
            league_id=num(q.get("leagueId")),
            team_id=num(q.get("teamId")),
            items_per_page=num(q.get("itemsPerPage")),
            page=num(q.get("page")),
        ),
    ),
    (re.compile(r"/api/live"), lambda c, m, q: c.get_live_games()),
    (
        re.compile(r"/api/teams/(\d+)/injuries"),
        lambda c, m, q: c.get_team_injuries(int(m[1])),
    ),
    (
        re.compile(r"/api/teams/(\d+)/stats"),
        lambda c, m, q: c.get_team_stats(int(m[1])),
    ),
    (
        re.compile(r"/api/odds"),
        lambda c, m, q: c.get_odds(
            from_=q.get("from", ""), to=q.get("to", ""), game_id=num(q.get("gameId"))
        ),
    ),
    (
        re.compile(r"/api/standings/(\d+)"),
        lambda c, m, q: c.get_standings(int(m[1])),
    ),
]


def make_handler(client: BaseballClient) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            url = urlsplit(self.path)
            if url.path in ("/", "/index.html"):
                self._send(200, (PUBLIC_DIR / "index.html").read_bytes(), "text/html")
                return
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            for pattern, route in ROUTES:
                match = pattern.fullmatch(url.path)
                if match:
                    self._run(partial(route, client, match, query))
                    return
            self._send_json(404, {"ok": False, "message": "Not found"})

        def _run(self, fn: Callable[[], Any]) -> None:
            started = time.monotonic()

            def elapsed() -> int:
                return round((time.monotonic() - started) * 1000)

            try:
                data = fn()
            except BaseballApiError as err:
                self._send_json(
                    err.status or 500,
                    {
                        "ok": False,
                        "ms": elapsed(),
                        "status": err.status,
                        "code": err.code,
                        "message": err.message,
                        "body": err.body,
                    },
                )
                return
            except Exception as err:  # server boundary: report instead of dropping
                self._send_json(
                    500, {"ok": False, "ms": elapsed(), "message": str(err)}
                )
                return
            self._send_json(200, {"ok": True, "ms": elapsed(), "data": data})

        def _send_json(self, status: int, payload: Any) -> None:
            self._send(status, json.dumps(payload).encode(), "application/json")

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main() -> None:
    api_key = os.environ.get("APIBASEBALL_KEY")
    if not api_key:
        raise SystemExit("Missing APIBASEBALL_KEY env var")

    port = int(os.environ.get("PORT") or 3000)
    server = ThreadingHTTPServer(
        ("127.0.0.1", port), make_handler(BaseballClient(api_key))
    )
    print(f"Dashboard: http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
