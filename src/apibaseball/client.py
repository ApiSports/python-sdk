"""The :class:`BaseballClient` and its parameter types."""

from datetime import date
from typing import Literal, Required, TypedDict

from ._http import (
    DEFAULT_BASE_URL,
    AuthIn,
    HttpClientConfig,
    Transport,
    as_paginated,
    format_value,
    request,
    urllib_transport,
)
from .types.baseball import (
    BaseballGame,
    BaseballLiveLeagueGroup,
    BaseballOdds,
    BaseballPlayer,
    BaseballStandings,
    BaseballTeamInjury,
    BaseballTeamStats,
)
from .types.common import ApiResponse, Country, League, Paginated, Team


class BaseballClientConfig(TypedDict, total=False):
    """Keyword arguments accepted by :class:`BaseballClient`.

    Useful for building configuration up front: ``BaseballClient(**config)``.
    """

    api_key: Required[str]
    base_url: str | None
    auth_in: AuthIn | None
    transport: Transport | None
    timeout: float | None


class GetLeaguesParams(TypedDict, total=False):
    """Keyword arguments for :meth:`BaseballClient.get_leagues`."""

    items_per_page: int | Literal["*"] | None
    page: int | None


class GetPlayersParams(TypedDict, total=False):
    """Keyword arguments for :meth:`BaseballClient.get_players`."""

    team_id: int | None
    league_id: int | None


class GetGamesParams(TypedDict, total=False):
    """Keyword arguments for :meth:`BaseballClient.get_games`.

    ``from_`` and ``to`` are required.
    """

    from_: Required[str | date]
    to: Required[str | date]
    league_id: int | None
    team_id: int | None
    items_per_page: int | None
    page: int | None


class GetOddsParams(TypedDict, total=False):
    """Keyword arguments for :meth:`BaseballClient.get_odds`.

    ``from_`` and ``to`` are required.
    """

    from_: Required[str | date]
    to: Required[str | date]
    game_id: int | None


class BaseballClient:
    """Typed client for the API Baseball REST API (11 GET endpoints).

    Every method returns the unwrapped ``result`` of the API envelope, or a
    :class:`~apibaseball.Paginated` dict for paginated endpoints, and raises
    :class:`~apibaseball.BaseballApiError` when a request fails.

    Args:
        api_key: Your API key.
        base_url: API base URL. Defaults to ``https://api.api-baseball.com/api``.
        auth_in: Where to send the API key: ``"header"`` (``X-Api-Key``, the
            default) or ``"query"`` (``api_key``).
        transport: Custom :data:`~apibaseball.Transport` (useful for tests,
            proxies or logging). Defaults to a standard-library transport.
        timeout: Request timeout in seconds. ``None`` (default) or ``0``
            disables it.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        auth_in: AuthIn | None = None,
        transport: Transport | None = None,
        timeout: float | None = None,
    ) -> None:
        self._config = HttpClientConfig(
            api_key=api_key,
            base_url=base_url if base_url is not None else DEFAULT_BASE_URL,
            auth_in=auth_in if auth_in is not None else "header",
            transport=transport if transport is not None else urllib_transport,
            timeout=timeout,
        )

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(base_url={self._config.base_url!r}, "
            f"auth_in={self._config.auth_in!r})"
        )

    def get_countries(self) -> list[Country]:
        """``GET /baseball/countries`` — countries with baseball leagues."""
        response: ApiResponse[list[Country]] = request(
            self._config, "/baseball/countries"
        )
        return response["result"]

    def get_leagues(
        self,
        *,
        items_per_page: int | Literal["*"] | None = None,
        page: int | None = None,
    ) -> Paginated[list[League]]:
        """``GET /baseball/leagues`` — active leagues (paginated).

        Args:
            items_per_page: Page size, or ``"*"`` for all results. The API
                default is 15. Note: the API currently ignores this on
                ``/baseball/leagues`` and always serves 15 per page; iterate
                ``page`` up to ``pagination["last_page"]`` to get every league.
            page: Page number. The API default is 1.

        Raises:
            BaseballApiError: If the request fails or the response carries no
                pagination metadata.
        """
        response: ApiResponse[list[League]] = request(
            self._config,
            "/baseball/leagues",
            {"items_per_page": items_per_page, "page": page},
        )
        return as_paginated(response)

    def get_leagues_by_country(self, country_id: int) -> list[League]:
        """``GET /baseball/countries/{format_value(country_id)}/leagues``."""
        response: ApiResponse[list[League]] = request(
            self._config, f"/baseball/countries/{format_value(country_id)}/leagues"
        )
        return response["result"]

    def get_teams_by_league(self, league_id: int) -> list[Team]:
        """``GET /baseball/leagues/{format_value(league_id)}/teams``."""
        response: ApiResponse[list[Team]] = request(
            self._config, f"/baseball/leagues/{format_value(league_id)}/teams"
        )
        return response["result"]

    def get_players(
        self,
        *,
        team_id: int | None = None,
        league_id: int | None = None,
    ) -> list[BaseballPlayer]:
        """``GET /baseball/players`` — optionally filtered by team and/or league."""
        response: ApiResponse[list[BaseballPlayer]] = request(
            self._config,
            "/baseball/players",
            {"team_id": team_id, "league_id": league_id},
        )
        return response["result"]

    def get_games(
        self,
        *,
        from_: str | date,
        to: str | date,
        league_id: int | None = None,
        team_id: int | None = None,
        items_per_page: int | None = None,
        page: int | None = None,
    ) -> Paginated[list[BaseballGame]]:
        """``GET /baseball/games`` — games in a date range (paginated).

        Args:
            from_: Start date (``YYYY-MM-DD`` string or :class:`datetime.date`).
                Sent as the ``from`` query parameter.
            to: End date (``YYYY-MM-DD`` string or :class:`datetime.date`).
                The API allows at most a 6-month range.
            league_id: Filter by league.
            team_id: Filter by team.
            items_per_page: Page size (max 500). The API default is 100.
            page: Page number.

        Raises:
            BaseballApiError: If the request fails or the response carries no
                pagination metadata.
        """
        response: ApiResponse[list[BaseballGame]] = request(
            self._config,
            "/baseball/games",
            {
                "from": from_,
                "to": to,
                "league_id": league_id,
                "team_id": team_id,
                "items_per_page": items_per_page,
                "page": page,
            },
        )
        return as_paginated(response)

    def get_live_games(self) -> list[BaseballLiveLeagueGroup]:
        """``GET /baseball/live`` — live games grouped by league."""
        response: ApiResponse[list[BaseballLiveLeagueGroup]] = request(
            self._config, "/baseball/live"
        )
        return response["result"]

    def get_team_injuries(self, team_id: int) -> list[BaseballTeamInjury]:
        """``GET /baseball/teams/{format_value(team_id)}/injuries``."""
        response: ApiResponse[list[BaseballTeamInjury]] = request(
            self._config, f"/baseball/teams/{format_value(team_id)}/injuries"
        )
        return response["result"]

    def get_team_stats(self, team_id: int) -> BaseballTeamStats:
        """``GET /baseball/teams/{format_value(team_id)}/stats``."""
        response: ApiResponse[BaseballTeamStats] = request(
            self._config, f"/baseball/teams/{format_value(team_id)}/stats"
        )
        return response["result"]

    def get_odds(
        self,
        *,
        from_: str | date,
        to: str | date,
        game_id: int | None = None,
    ) -> list[BaseballOdds]:
        """``GET /baseball/odds`` — pre-match odds.

        Args:
            from_: Start date (``YYYY-MM-DD`` string or :class:`datetime.date`).
                Sent as the ``from`` query parameter.
            to: End date (``YYYY-MM-DD`` string or :class:`datetime.date`).
                The API allows at most a 5-day range.
            game_id: Filter by game.
        """
        response: ApiResponse[list[BaseballOdds]] = request(
            self._config,
            "/baseball/odds",
            {"from": from_, "to": to, "game_id": game_id},
        )
        return response["result"]

    def get_standings(self, league_id: int) -> BaseballStandings:
        """``GET /baseball/leagues/{format_value(league_id)}/standings``."""
        response: ApiResponse[BaseballStandings] = request(
            self._config, f"/baseball/leagues/{format_value(league_id)}/standings"
        )
        return response["result"]
