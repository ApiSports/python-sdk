"""Live tests against the real API.

Skipped unless ``APIBASEBALL_KEY`` is set (in the environment or in a ``.env``
file next to ``pyproject.toml``). Run only these with ``pytest -m live``.

Besides checking that every method succeeds, each response is validated
against the SDK's ``TypedDict`` models, so drift between the real payloads and
the declared types shows up as a failure listing the offending JSON paths.
"""

import os
import types
import typing
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints

import pytest

from apibaseball import (
    BaseballApiError,
    BaseballClient,
    BaseballGame,
    BaseballLiveLeagueGroup,
    BaseballOdds,
    BaseballPlayer,
    BaseballStandings,
    BaseballTeamInjury,
    BaseballTeamStats,
    Country,
    League,
    Pagination,
    Team,
)


def _load_key() -> str | None:
    key = os.environ.get("APIBASEBALL_KEY")
    if key:
        return key.strip()
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            name, sep, value = line.partition("=")
            if sep and name.strip() == "APIBASEBALL_KEY":
                return value.strip().strip("\"'") or None
    return None


API_KEY = _load_key()

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not API_KEY, reason="APIBASEBALL_KEY is not set"),
]

TODAY = date.today()
WEEK_AGO = TODAY - timedelta(days=7)


# --- shape validation -------------------------------------------------------


def _is_typeddict(tp: Any) -> bool:
    return isinstance(tp, type) and typing.is_typeddict(tp)


def _check(value: Any, tp: Any, path: str, errors: list[str]) -> None:
    if tp is Any:
        return
    if tp is type(None):
        if value is not None:
            errors.append(f"{path}: expected null, got {value!r}")
        return
    origin = get_origin(tp)
    if origin in (Union, types.UnionType):
        for option in get_args(tp):
            attempt: list[str] = []
            _check(value, option, path, attempt)
            if not attempt:
                return
        errors.append(f"{path}: {value!r} matches none of {tp}")
        return
    if origin is Literal:
        if value not in get_args(tp):
            errors.append(f"{path}: {value!r} is not one of {get_args(tp)}")
        return
    if origin is list:
        if not isinstance(value, list):
            errors.append(f"{path}: expected list, got {type(value).__name__}")
            return
        (item_tp,) = get_args(tp)
        for i, item in enumerate(value):
            _check(item, item_tp, f"{path}[{i}]", errors)
        return
    if origin is dict:
        if not isinstance(value, dict):
            errors.append(f"{path}: expected object, got {type(value).__name__}")
            return
        _, value_tp = get_args(tp)
        for key, item in value.items():
            _check(item, value_tp, f"{path}.{key}", errors)
        return
    if _is_typeddict(tp):
        if not isinstance(value, dict):
            errors.append(f"{path}: expected object, got {type(value).__name__}")
            return
        hints = get_type_hints(tp)
        for key in tp.__required_keys__:
            if key not in value:
                errors.append(f"{path}.{key}: missing")
        for key, field_tp in hints.items():
            if key in value:
                _check(value[key], field_tp, f"{path}.{key}", errors)
        return
    if tp is float:
        ok = isinstance(value, int | float) and not isinstance(value, bool)
    elif tp is int:
        ok = isinstance(value, int) and not isinstance(value, bool)
    else:
        ok = isinstance(value, tp)
    if not ok:
        errors.append(f"{path}: expected {tp.__name__}, got {value!r}")


def assert_shape(value: Any, tp: Any, name: str) -> None:
    errors: list[str] = []
    _check(value, tp, name, errors)
    assert not errors, f"{len(errors)} mismatch(es):\n" + "\n".join(errors[:30])


# --- fixtures: discover real ids once, reuse them ---------------------------


@pytest.fixture(scope="module")
def client() -> BaseballClient:
    assert API_KEY
    return BaseballClient(API_KEY, timeout=30)


@pytest.fixture(scope="module")
def all_leagues(client: BaseballClient) -> list[League]:
    # The API ignores ``items_per_page`` on /leagues (even ``"*"``) and always
    # serves 15 per page, so walk every page.
    leagues: list[League] = []
    page = 1
    while True:
        response = client.get_leagues(page=page)
        leagues += response["result"]
        if page >= response["pagination"]["last_page"]:
            break
        page += 1
    assert leagues, "the API returned no leagues"
    return leagues


@pytest.fixture(scope="module")
def league(all_leagues: list[League]) -> League:
    """Prefer MLB, so standings/teams/players have data."""
    for candidate in all_leagues:
        if candidate["name"].strip().upper() == "MLB":
            return candidate
    return all_leagues[0]


@pytest.fixture(scope="module")
def teams(client: BaseballClient, league: League) -> list[Team]:
    teams = client.get_teams_by_league(league["id"])
    assert teams, f"league {league['id']} has no teams"
    return teams


@pytest.fixture(scope="module")
def team(teams: list[Team]) -> Team:
    return teams[0]


# --- one test per SDK method ------------------------------------------------


def test_get_countries(client: BaseballClient) -> None:
    countries = client.get_countries()
    assert countries
    assert_shape(countries, list[Country], "countries")


def test_get_leagues_paginated(client: BaseballClient) -> None:
    page = client.get_leagues(page=2)
    assert page["result"]
    assert_shape(page["result"], list[League], "leagues")
    assert_shape(page["pagination"], Pagination, "pagination")
    assert page["pagination"]["current_page"] == 2


def test_get_leagues_all(all_leagues: list[League]) -> None:
    assert_shape(all_leagues, list[League], "leagues")


def test_get_leagues_by_country(client: BaseballClient, league: League) -> None:
    leagues = client.get_leagues_by_country(league["country_id"])
    assert leagues
    assert_shape(leagues, list[League], "leagues")
    assert all(item["country_id"] == league["country_id"] for item in leagues)


def test_get_teams_by_league(teams: list[Team]) -> None:
    assert_shape(teams, list[Team], "teams")


def test_get_players_by_team(client: BaseballClient, team: Team) -> None:
    players = client.get_players(team_id=team["id"])
    assert_shape(players, list[BaseballPlayer], "players")


def test_get_players_by_league(client: BaseballClient, league: League) -> None:
    players = client.get_players(league_id=league["id"])
    assert_shape(players, list[BaseballPlayer], "players")


def test_get_games(client: BaseballClient, league: League) -> None:
    page = client.get_games(
        from_=WEEK_AGO, to=TODAY, league_id=league["id"], items_per_page=50
    )
    assert_shape(page["result"], list[BaseballGame], "games")
    assert_shape(page["pagination"], Pagination, "pagination")


def test_get_games_string_dates(client: BaseballClient) -> None:
    page = client.get_games(
        from_=WEEK_AGO.isoformat(), to=TODAY.isoformat(), items_per_page=5, page=1
    )
    assert len(page["result"]) <= 5
    assert_shape(page["result"], list[BaseballGame], "games")


def test_get_live_games(client: BaseballClient) -> None:
    groups = client.get_live_games()  # may legitimately be empty
    assert_shape(groups, list[BaseballLiveLeagueGroup], "live")


def test_get_team_injuries(client: BaseballClient, team: Team) -> None:
    injuries = client.get_team_injuries(team["id"])
    assert_shape(injuries, list[BaseballTeamInjury], "injuries")


def test_get_team_stats(client: BaseballClient, team: Team) -> None:
    stats = client.get_team_stats(team["id"])
    assert_shape(stats, BaseballTeamStats, "stats")


def test_get_odds(client: BaseballClient) -> None:
    odds = client.get_odds(from_=TODAY, to=TODAY + timedelta(days=3))
    assert_shape(odds, list[BaseballOdds], "odds")


def test_get_odds_by_game(client: BaseballClient) -> None:
    # The API rejects odds ranges longer than 5 days.
    until = TODAY + timedelta(days=4)
    odds = client.get_odds(from_=TODAY, to=until)
    if not odds:
        pytest.skip("no odds in the date range to pick a game from")
    game_id = odds[0]["game_id"]
    filtered = client.get_odds(from_=TODAY, to=until, game_id=game_id)
    assert filtered
    assert all(item["game_id"] == game_id for item in filtered)


def test_get_standings(client: BaseballClient, league: League) -> None:
    standings = client.get_standings(league["id"])
    assert_shape(standings, BaseballStandings, "standings")


# --- auth and errors --------------------------------------------------------


def test_query_auth(client: BaseballClient) -> None:
    assert API_KEY
    via_query = BaseballClient(API_KEY, auth_in="query", timeout=30)
    assert via_query.get_countries() == client.get_countries()


def test_invalid_key_raises_401() -> None:
    bad = BaseballClient("invalid-key-for-testing", timeout=30)
    with pytest.raises(BaseballApiError) as info:
        bad.get_countries()
    assert info.value.status == 401


def test_unknown_team_raises(client: BaseballClient) -> None:
    with pytest.raises(BaseballApiError) as info:
        client.get_team_stats(999_999_999)
    assert info.value.status != 0
