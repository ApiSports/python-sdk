"""Client-level tests: configuration, auth, and every endpoint method."""

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

import pytest
from conftest import API_KEY, PAGINATION, FakeTransport, MakeClient

from apibaseball import (
    DEFAULT_BASE_URL,
    BaseballApiError,
    BaseballClient,
    BaseballClientConfig,
    BaseballStandings,
    GetGamesParams,
    GetLeaguesParams,
    GetOddsParams,
    GetPlayersParams,
    League,
    Team,
)

LEAGUES: list[League] = [
    {
        "id": 10,
        "name": "MLB",
        "country": "USA",
        "year": "2026",
        "country_id": 1,
        "logo": None,
        "country_logo": None,
        "importance": 1,
        "date_start": "2026-03-01",
        "date_stop": "2026-10-01",
    }
]

TEAMS: list[Team] = [
    {
        "id": 99,
        "name": "Yankees",
        "slug": "yankees",
        "logo": None,
        "active": True,
        "venue_name": "Yankee Stadium",
        "venue_city": "New York",
        "venue_capacity": 54000,
    }
]


# --- configuration & authentication ----------------------------------------


def test_sends_x_api_key_header_by_default_and_returns_countries(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": [{"id": 1, "name": "USA", "logo": None}]})

    countries = make_client().get_countries()

    assert countries == [{"id": 1, "name": "USA", "logo": None}]
    assert len(transport.requests) == 1
    assert transport.last.url == f"{DEFAULT_BASE_URL}/baseball/countries"
    assert transport.last.method == "GET"
    assert transport.last.headers == {
        "Accept": "application/json",
        "X-Api-Key": API_KEY,
    }
    assert transport.last.timeout is None


def test_puts_api_key_in_query_when_auth_in_is_query(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": []})

    make_client(auth_in="query").get_live_games()

    assert transport.last.url == f"{DEFAULT_BASE_URL}/baseball/live?api_key={API_KEY}"
    assert "X-Api-Key" not in transport.last.headers


def test_query_auth_appends_api_key_after_other_params(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": []})

    make_client(auth_in="query").get_players(team_id=3)

    assert transport.last.url.endswith(
        "/baseball/players?team_id=3&api_key=test-api-key"
    )


def test_uses_custom_base_url_with_trailing_slash(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": []})

    make_client(base_url="https://example.test/v1/").get_players(team_id=3)

    assert transport.last.url == "https://example.test/v1/baseball/players?team_id=3"


def test_none_config_values_fall_back_to_defaults(transport: FakeTransport) -> None:
    transport.reply({"success": 1, "result": []})
    client = BaseballClient(
        API_KEY, base_url=None, auth_in=None, transport=transport, timeout=None
    )

    client.get_countries()

    assert transport.last.url == f"{DEFAULT_BASE_URL}/baseball/countries"
    assert transport.last.headers["X-Api-Key"] == API_KEY


def test_accepts_config_dict(transport: FakeTransport) -> None:
    transport.reply({"success": 1, "result": []})
    config: BaseballClientConfig = {
        "api_key": API_KEY,
        "transport": transport,
        "auth_in": "query",
    }

    BaseballClient(**config).get_countries()

    assert "api_key=test-api-key" in transport.last.url


def test_api_key_is_required() -> None:
    with pytest.raises(TypeError):
        BaseballClient()  # type: ignore[call-arg]


def test_repr_does_not_leak_api_key(make_client: MakeClient) -> None:
    client = make_client()
    assert API_KEY not in repr(client)
    assert API_KEY not in repr(client._config)


@pytest.mark.parametrize(
    ("timeout", "expected"), [(None, None), (0, None), (-1, None), (2.5, 2.5)]
)
def test_timeout_is_passed_to_transport_in_seconds(
    transport: FakeTransport,
    make_client: MakeClient,
    timeout: float | None,
    expected: float | None,
) -> None:
    transport.reply({"success": 1, "result": []})

    make_client(timeout=timeout).get_countries()

    assert transport.last.timeout == expected


# --- endpoints --------------------------------------------------------------

Call = Callable[[BaseballClient], Any]

# (method call, expected path + query) for every non-paginated endpoint.
SIMPLE_ENDPOINTS: list[tuple[str, Call, str]] = [
    ("get_countries", lambda c: c.get_countries(), "/baseball/countries"),
    (
        "get_leagues_by_country",
        lambda c: c.get_leagues_by_country(7),
        "/baseball/countries/7/leagues",
    ),
    (
        "get_teams_by_league",
        lambda c: c.get_teams_by_league(42),
        "/baseball/leagues/42/teams",
    ),
    ("get_players", lambda c: c.get_players(), "/baseball/players"),
    (
        "get_players(filters)",
        lambda c: c.get_players(team_id=1, league_id=2),
        "/baseball/players?team_id=1&league_id=2",
    ),
    ("get_live_games", lambda c: c.get_live_games(), "/baseball/live"),
    (
        "get_team_injuries",
        lambda c: c.get_team_injuries(5),
        "/baseball/teams/5/injuries",
    ),
    ("get_team_stats", lambda c: c.get_team_stats(5), "/baseball/teams/5/stats"),
    (
        "get_odds",
        lambda c: c.get_odds(from_="2026-07-01", to="2026-07-05"),
        "/baseball/odds?from=2026-07-01&to=2026-07-05",
    ),
    (
        "get_odds(game_id)",
        lambda c: c.get_odds(from_="2026-07-01", to="2026-07-05", game_id=9),
        "/baseball/odds?from=2026-07-01&to=2026-07-05&game_id=9",
    ),
    (
        "get_standings",
        lambda c: c.get_standings(1),
        "/baseball/leagues/1/standings",
    ),
]


@pytest.mark.parametrize(
    ("call", "path"),
    [(call, path) for _, call, path in SIMPLE_ENDPOINTS],
    ids=[name for name, _, _ in SIMPLE_ENDPOINTS],
)
def test_simple_endpoints_build_url_and_unwrap_result(
    transport: FakeTransport, make_client: MakeClient, call: Call, path: str
) -> None:
    payload = {"marker": "result"}
    transport.reply({"success": 1, "result": payload})

    assert call(make_client()) == payload
    assert transport.last.url == f"{DEFAULT_BASE_URL}{path}"
    assert transport.last.method == "GET"


def test_get_teams_by_league_returns_teams(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": TEAMS})

    assert make_client().get_teams_by_league(42) == TEAMS
    assert transport.last.url == f"{DEFAULT_BASE_URL}/baseball/leagues/42/teams"


def test_get_standings_returns_payload(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    standings: BaseballStandings = {
        "league": {"id": 1, "name": "MLB", "logo": None},
        "standings": {
            "AL East": [
                {
                    "position": 1,
                    "team_id": 99,
                    "team_name": "Yankees",
                    "team_logo": None,
                    "division": "AL East",
                    "games_played": 10,
                    "wins": 7,
                    "losses": 3,
                    "draws": 0,
                    "win_percentage": "0.700",
                    "points_for": 50,
                    "points_against": 30,
                    "recent_form": "WWLWW",
                }
            ]
        },
    }
    transport.reply({"success": 1, "result": standings})

    assert make_client().get_standings(1) == standings


def test_get_leagues_returns_paginated_and_serializes_query(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": LEAGUES, "pagination": PAGINATION})

    result = make_client().get_leagues(items_per_page=15, page=2)

    assert result == {"result": LEAGUES, "pagination": PAGINATION}
    assert transport.last.url == (
        f"{DEFAULT_BASE_URL}/baseball/leagues?items_per_page=15&page=2"
    )


def test_get_leagues_without_params(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": [], "pagination": PAGINATION})

    make_client().get_leagues()

    assert transport.last.url == f"{DEFAULT_BASE_URL}/baseball/leagues"


def test_get_leagues_star_is_sent_unencoded(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": [], "pagination": PAGINATION})

    make_client().get_leagues(items_per_page="*")

    assert transport.last.url == f"{DEFAULT_BASE_URL}/baseball/leagues?items_per_page=*"


def test_get_leagues_star_without_pagination_raises(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    # Same as the TypeScript SDK: paginated methods require pagination metadata.
    transport.reply({"success": 1, "result": LEAGUES})

    with pytest.raises(BaseballApiError) as info:
        make_client().get_leagues(items_per_page="*")

    assert info.value.message == "Expected pagination metadata in API response"
    assert info.value.status == 0
    assert info.value.body == {"success": 1, "result": LEAGUES}


def test_get_games_omits_none_query_params(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": [], "pagination": PAGINATION})

    make_client().get_games(from_="2026-07-01", to="2026-07-07", league_id=5)

    assert transport.last.url == (
        f"{DEFAULT_BASE_URL}/baseball/games?from=2026-07-01&to=2026-07-07&league_id=5"
    )
    assert "team_id" not in transport.last.url
    assert "items_per_page" not in transport.last.url
    assert "page=" not in transport.last.url


def test_get_games_sends_all_params_in_order(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": [], "pagination": PAGINATION})

    result: object = make_client().get_games(
        from_="2026-07-01",
        to="2026-07-07",
        league_id=5,
        team_id=6,
        items_per_page=500,
        page=3,
    )

    assert result == {"result": [], "pagination": PAGINATION}
    assert transport.last.url == (
        f"{DEFAULT_BASE_URL}/baseball/games?from=2026-07-01&to=2026-07-07"
        "&league_id=5&team_id=6&items_per_page=500&page=3"
    )


def test_get_games_accepts_date_objects(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": [], "pagination": PAGINATION})

    make_client().get_games(from_=date(2026, 7, 1), to=datetime(2026, 7, 7, 13, 30))

    assert transport.last.url.endswith("/baseball/games?from=2026-07-01&to=2026-07-07")


def test_get_odds_accepts_date_objects(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": []})

    make_client().get_odds(from_=date(2026, 7, 1), to=date(2026, 7, 5))

    assert transport.last.url.endswith("/baseball/odds?from=2026-07-01&to=2026-07-05")


def test_get_games_without_pagination_raises(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": []})

    with pytest.raises(BaseballApiError, match="Expected pagination metadata"):
        make_client().get_games(from_="2026-07-01", to="2026-07-07")


def test_null_pagination_raises(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": [], "pagination": None})

    with pytest.raises(BaseballApiError, match="Expected pagination metadata"):
        make_client().get_leagues()


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_games(to="2026-07-07"),
        lambda c: c.get_games(from_="2026-07-01"),
        lambda c: c.get_odds(to="2026-07-05"),
        lambda c: c.get_odds(from_="2026-07-01"),
        lambda c: c.get_leagues_by_country(),
        lambda c: c.get_teams_by_league(),
        lambda c: c.get_team_injuries(),
        lambda c: c.get_team_stats(),
        lambda c: c.get_standings(),
    ],
)
def test_required_params_are_enforced(
    transport: FakeTransport, make_client: MakeClient, call: Call
) -> None:
    with pytest.raises(TypeError):
        call(make_client())
    assert transport.requests == []


def test_filter_params_are_keyword_only(make_client: MakeClient) -> None:
    client = make_client()
    with pytest.raises(TypeError):
        client.get_players(1)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        client.get_games("2026-07-01", "2026-07-07")  # type: ignore[call-arg]


def test_param_typed_dicts_unpack_into_methods(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": [], "pagination": PAGINATION})
    client = make_client()

    leagues: GetLeaguesParams = {"page": 2}
    client.get_leagues(**leagues)
    assert transport.last.url.endswith("/baseball/leagues?page=2")

    games: GetGamesParams = {"from_": "2026-07-01", "to": "2026-07-02", "team_id": 4}
    client.get_games(**games)
    assert transport.last.url.endswith("?from=2026-07-01&to=2026-07-02&team_id=4")

    players: GetPlayersParams = {"league_id": 8}
    client.get_players(**players)
    assert transport.last.url.endswith("/baseball/players?league_id=8")

    odds: GetOddsParams = {"from_": "2026-07-01", "to": "2026-07-02", "game_id": 1}
    client.get_odds(**odds)
    assert transport.last.url.endswith("?from=2026-07-01&to=2026-07-02&game_id=1")
