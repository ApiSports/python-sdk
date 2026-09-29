"""Baseball-specific response shapes (games, live, odds, standings, stats).

As in :mod:`apibaseball.types.common`, these are :class:`~typing.TypedDict`
descriptions of the decoded JSON; values are plain ``dict``/``list`` objects.
"""

from typing import Literal, TypedDict


class BaseballGameLeague(TypedDict):
    """Nested league ref on a game (``BaseballGameResource.league``)."""

    id: int
    name: str


class BaseballGameTournament(TypedDict):
    """Nested tournament ref on a game (``BaseballGameResource.tournament``)."""

    id: int
    name: str
    season: str


class BaseballGameTeam(TypedDict):
    """Nested team ref on a scheduled/finished game."""

    id: int
    name: str
    logo: str | None


class BaseballGameScoreMap(TypedDict):
    """Score block embedded on ``BaseballGameResource``.

    ``innings`` usually comes as an ordered list (``None`` for innings not
    played), but some games return a dict keyed by inning number, which may also
    carry an ``"extra"`` entry as a string (e.g. ``{"1": 0, ..., "extra": "1"}``).
    """

    total: int
    hits: int
    errors: int
    innings: list[int | None] | dict[str, int | str]


class BaseballGameVenue(TypedDict):
    """Nested venue ref on a scheduled/finished game."""

    id: int
    name: str


class BaseballGame(TypedDict):
    """Baseball game (``BaseballGameResource``)."""

    id: int
    date: str
    time: str
    status: str
    stage: str | None
    live: bool
    extra_innings: bool
    total_score: str | None
    league: BaseballGameLeague | None
    tournament: BaseballGameTournament | None
    home_team: BaseballGameTeam | None
    away_team: BaseballGameTeam | None
    home_score: BaseballGameScoreMap | None
    away_score: BaseballGameScoreMap | None
    venue: BaseballGameVenue | None


class BaseballGameScore(TypedDict):
    """Live/box score (``BaseballGameScore``) with innings as an ordered list."""

    total: int
    hits: int
    errors: int
    innings: list[int | None]
    extra: int | None


class BaseballLiveTeam(TypedDict):
    """Team block on a live game (``BaseballLiveTeam``)."""

    id: int
    name: str
    logo: str | None
    score: BaseballGameScore | None


class BaseballLiveVenue(TypedDict):
    """Venue block on a live game."""

    name: str | None
    city: str | None


class BaseballLiveGame(TypedDict):
    """Live game (``BaseballLiveGame``)."""

    id: int
    date: str
    time: str
    status: str
    stage: str | None
    extra_innings: bool
    total_score: str | None
    venue: BaseballLiveVenue
    home_team: BaseballLiveTeam
    away_team: BaseballLiveTeam


class BaseballLiveLeagueGroup(TypedDict):
    """Live games grouped by league (``BaseballLiveLeagueGroup``)."""

    league_id: int
    league_name: str
    league_logo: str | None
    games: list[BaseballLiveGame]


class BaseballOddsPrice(TypedDict):
    """One bookmaker's price for an outcome, as strings.

    For example ``{"decimal": "2.800", "us": "180"}``.
    """

    decimal: str
    us: str


BaseballOddsOutcome = dict[str, BaseballOddsPrice]
"""Prices for one outcome, keyed by bookmaker name (e.g. ``"bet365"``)."""

BaseballOddsMarket = dict[str, BaseballOddsOutcome]
"""One market, keyed by outcome name (e.g. ``"Home"``, ``"Away"``, ``"Over"``)."""


class BaseballOdds(TypedDict):
    """Pre-match odds for a game (``/baseball/odds``).

    ``odds`` is keyed by market name (e.g. ``"3Way Result"``, ``"Home/Away"``),
    then outcome, then bookmaker: ``odds["Home/Away"]["Home"]["bet365"]["decimal"]``.
    """

    game_id: int
    home_team: str
    away_team: str
    odds: dict[str, BaseballOddsMarket]


class BaseballStanding(TypedDict):
    """Standing row within a division (``/baseball/leagues/{id}/standings``)."""

    position: int
    team_id: int
    team_name: str
    team_logo: str | None
    division: str | None
    games_played: int
    wins: int
    losses: int
    draws: int
    win_percentage: str
    """Win percentage as returned by the API, e.g. ``"0.528"``."""
    points_for: int
    points_against: int
    recent_form: str | None
    """Recent results, e.g. ``"WLWWL"``."""


class BaseballStandingsLeague(TypedDict):
    """League summary on a standings response."""

    id: int
    name: str
    logo: str | None


class BaseballStandings(TypedDict):
    """Standings payload: league info plus rows grouped by division name.

    For example ``"AL East"`` maps to a list of :class:`BaseballStanding`.
    """

    league: BaseballStandingsLeague
    standings: dict[str, list[BaseballStanding]]


class BaseballTeamInjury(TypedDict):
    """Team injury report (``BaseballTeamInjuryResource``)."""

    id: int
    player_id: int | None
    player_name: str
    report_date: str | None
    status: str | None
    description: str | None
    team_id: int
    team_name: str | None
    team_logo: str | None


class BaseballTeamStatsBatting(TypedDict):
    """Team batting stats (``BaseballTeamStatsBatting``)."""

    rank: int
    games_played: int
    at_bats: int
    runs: int
    hits: int
    doubles: int
    triples: int
    home_runs: int
    runs_batted_in: int
    batting_avg: str
    on_base_percentage: str
    slugging_percentage: str


class BaseballTeamStatsPitching(TypedDict):
    """Team pitching stats (``BaseballTeamStatsPitching``)."""

    rank: int
    games_played: int
    quality_starts: int
    innings_pitched: str
    hits: int
    earned_runs: int
    home_runs: int
    walks: int
    strikeouts: int
    wins: int
    losses: int
    saves: int
    earned_run_avg: str


class BaseballTeamStatsFielding(TypedDict):
    """Team fielding stats (``BaseballTeamStatsFielding``)."""

    rank: int
    games_played: int
    total_chances: int
    putouts: int
    assists: int
    errors: int
    fielding_pct: str


class BaseballTeamStats(TypedDict):
    """Aggregated team stats (``BaseballTeamStatsResource``)."""

    team_id: int
    team_name: str
    team_logo: str | None
    batting: BaseballTeamStatsBatting | None
    pitching: BaseballTeamStatsPitching | None
    fielding: BaseballTeamStatsFielding | None


class BaseballPlayerStatsBase(TypedDict):
    """Shared fields across player season stat lines."""

    season: int
    position: str | None
    rank: int | None
    games_played: int
    team_id: int | None
    team_name: str | None
    league_id: int | None


class BaseballPlayerStatsBatting(BaseballPlayerStatsBase):
    """Player batting stats (``BaseballPlayerStatsBatting``)."""

    type: Literal["batting"]
    at_bats: int
    runs: int
    hits: int
    doubles: int
    triples: int
    home_runs: int
    total_bases: int | None
    runs_batted_in: int
    walks: int
    strikeouts: int
    stolen_bases: int
    caught_stealing: int | None
    batting_avg: str
    on_base_percentage: str
    slugging_percentage: str


class BaseballPlayerStatsPitching(BaseballPlayerStatsBase):
    """Player pitching stats (``BaseballPlayerStatsPitching``)."""

    type: Literal["pitching"]
    games_started: int | None
    wins: int
    losses: int
    saves: int
    quality_starts: int | None
    holds: int
    innings_pitched: str
    earned_runs: int
    strikeouts: int
    walks: int
    strikeouts_per_9_innings: str | None
    pitches_per_start: str | None
    earned_run_average: str | None
    walk_hits_per_inning_pitched: str | None


class BaseballPlayerStatsFielding(BaseballPlayerStatsBase):
    """Player fielding stats (``BaseballPlayerStatsFielding``)."""

    type: Literal["fielding"]
    full_innings: int | None
    total_chances: int
    putouts: int
    assists: int
    errors: str
    """Fielding errors value as returned by the API (string in the OpenAPI schema)."""
    double_plays: int
    fielding_percentage: str
    range_factor: str
    zone_rating: str | None


BaseballPlayerStats = (
    BaseballPlayerStatsBatting
    | BaseballPlayerStatsPitching
    | BaseballPlayerStatsFielding
)
"""Union of player season stat lines, discriminated by ``type``."""


class BaseballPlayer(TypedDict):
    """Baseball player with optional season stats (``BaseballPlayerResource``)."""

    id: int
    name: str
    number: str | None
    position: str | None
    bats_hand: str | None
    throws_hand: str | None
    age: int | None
    height: str | None
    weight: str | None
    active: bool
    team_id: int | None
    team_name: str | None
    team_logo: str | None
    league_id: int | None
    league_name: str | None
    league_logo: str | None
    stats: list[BaseballPlayerStats]
