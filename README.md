# apibaseball

Python SDK for the [API Baseball](https://api-baseball.com) REST API. Zero runtime dependencies — uses the standard library's `urllib`.

This is the Python counterpart of the TypeScript `apibaseball` package and exposes the same endpoints, options and error behavior (see [Differences from the TypeScript SDK](#differences-from-the-typescript-sdk)).

## Install

```bash
pip install apibaseball
```

Requires **Python 3.11+**.

## Quick start

```python
import os
from apibaseball import BaseballClient

client = BaseballClient(api_key=os.environ["APIBASEBALL_KEY"])

leagues = client.get_leagues(page=1)
games = client.get_games(from_="2026-07-01", to="2026-07-07")
```

## Authentication

Pass your API key when constructing the client. By default it is sent as the `X-Api-Key` header.

```python
client = BaseballClient(api_key="your-api-key")
```

To send the key as a query parameter (`api_key`) instead:

```python
client = BaseballClient(api_key="your-api-key", auth_in="query")
```

## Configuration

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `api_key` | `str` | — | **Required.** Your API key. |
| `base_url` | `str` | `https://api.api-baseball.com/api` | API base URL. |
| `auth_in` | `"header"` \| `"query"` | `"header"` | Where to send the API key (`X-Api-Key` or `api_key`). |
| `transport` | `Transport` | `urllib_transport` | Custom transport (useful for tests, proxies or logging). |
| `timeout` | `float` | disabled | Request timeout in **seconds**, applied to each socket operation (connect, each read) by the default transport. `None` or `0` disables it. |

Options can also be collected in a `BaseballClientConfig` dict and passed as `BaseballClient(**config)`.

### Custom transport

A transport is any callable that takes an `HttpRequest` and returns an `HttpResponse`. It must return a response for every HTTP status (including 4xx/5xx), raise `TimeoutError` on timeouts and another `OSError` on network failures.

```python
from apibaseball import BaseballClient, HttpRequest, HttpResponse, urllib_transport


def logging_transport(request: HttpRequest) -> HttpResponse:
    response = urllib_transport(request)
    print(request.method, response.status)
    return response


client = BaseballClient(api_key="your-api-key", transport=logging_transport)
```

## API methods

All methods return the unwrapped `result` (or a `Paginated` dict for paginated endpoints). Filter parameters are keyword-only. Dates accept `YYYY-MM-DD` strings or `datetime.date` objects.

| Method | Endpoint |
| --- | --- |
| `get_countries()` | `GET /baseball/countries` |
| `get_leagues(*, items_per_page=None, page=None)` | `GET /baseball/leagues` |
| `get_leagues_by_country(country_id)` | `GET /baseball/countries/{country_id}/leagues` |
| `get_teams_by_league(league_id)` | `GET /baseball/leagues/{league_id}/teams` |
| `get_players(*, team_id=None, league_id=None)` | `GET /baseball/players` |
| `get_games(*, from_, to, league_id=None, team_id=None, items_per_page=None, page=None)` | `GET /baseball/games` |
| `get_live_games()` | `GET /baseball/live` |
| `get_team_injuries(team_id)` | `GET /baseball/teams/{team_id}/injuries` |
| `get_team_stats(team_id)` | `GET /baseball/teams/{team_id}/stats` |
| `get_odds(*, from_, to, game_id=None)` | `GET /baseball/odds` |
| `get_standings(league_id)` | `GET /baseball/leagues/{league_id}/standings` |

`from` is a Python keyword, so the start date is passed as `from_`; it is still sent to the API as the `from` query parameter.

### Examples

```python
from datetime import date

# Countries & leagues
countries = client.get_countries()
page = client.get_leagues(page=1, items_per_page=50)
leagues, pagination = page["result"], page["pagination"]
us_leagues = client.get_leagues_by_country(countries[0]["id"])

# Teams & players
teams = client.get_teams_by_league(us_leagues[0]["id"])
players = client.get_players(team_id=teams[0]["id"])

# Games (from_/to required; max 6 months range)
games = client.get_games(
    from_=date(2026, 7, 1),
    to=date(2026, 7, 7),
    league_id=us_leagues[0]["id"],
)["result"]

# Live games
live = client.get_live_games()

# Team injuries & stats
injuries = client.get_team_injuries(teams[0]["id"])
stats = client.get_team_stats(teams[0]["id"])

# Odds (from_/to required; max 5 days range)
odds = client.get_odds(from_="2026-07-01", to="2026-07-05")

# Standings
standings = client.get_standings(us_leagues[0]["id"])
```

### Response types

Responses are plain `dict`/`list` values decoded from JSON. Every shape is described by a `TypedDict` exported from the package (`Country`, `League`, `Team`, `BaseballGame`, `BaseballPlayer`, `BaseballOdds`, `BaseballStandings`, …), so type checkers and IDEs know the available keys.

### Pagination

Paginated methods (`get_leagues`, `get_games`) return:

```python
class Paginated(TypedDict, Generic[T]):
    result: T
    pagination: Pagination  # current_page, per_page, total, last_page, from, to
```

For `get_leagues`, the API currently ignores `items_per_page` (including `"*"`) and always returns 15 leagues per page. To fetch every league, iterate `page` up to `pagination["last_page"]`:

```python
leagues = []
page = 1
while True:
    response = client.get_leagues(page=page)
    leagues += response["result"]
    if page >= response["pagination"]["last_page"]:
        break
    page += 1
```

If the API omits pagination metadata, `BaseballApiError("Expected pagination metadata in API response")` is raised, the same as in the TypeScript SDK.

`get_odds` accepts a date range of at most 5 days; longer ranges are rejected by the API with a `BaseballApiError`.

## Error handling

Failed requests raise `BaseballApiError` when:

- HTTP status is `>= 400`
- The response envelope does not signal success (`success` is not `1`/`true`/`"1"`, and there is no `message: "Success"`)
- The request times out (if `timeout` is set) or a network error occurs
- The body is not a JSON object

```python
from apibaseball import BaseballApiError, BaseballClient

try:
    client.get_games(from_="2026-07-01", to="2026-07-07")
except BaseballApiError as err:
    print(err.message, err.status, err.code)
    raise
```

| Attribute | Description |
| --- | --- |
| `message` | Error message (also `str(err)`). |
| `status` | HTTP status (`0` if the request never completed, e.g. timeout). |
| `code` | Optional API error code from the response body. |
| `body` | Raw response body when available. |

The underlying exception (timeout, network error) is chained as `err.__cause__`.

## Differences from the TypeScript SDK

The request/response behavior matches the TypeScript SDK. The differences are Python conventions:

- Method and parameter names are `snake_case` (`getGames({ itemsPerPage })` → `get_games(items_per_page=...)`), and the start date is `from_`.
- The client is synchronous; there are no promises and no per-request abort signal.
- `timeout` is in seconds (TypeScript: `timeoutMs` in milliseconds). Any `TimeoutError` raised while a timeout is configured is reported as `Request timed out after <timeout>s`.
- A pluggable `transport` replaces the `fetch` option. The default transport sends `User-Agent: apibaseball-python/<version>`.
- Date parameters also accept `datetime.date` objects.
- Network error messages never contain the API key (it is shown as `***`); if the underlying exception mentions the key, it is not chained as `__cause__`. An empty network error message becomes `"Network request failed"`.
- `repr()` of the client, `HttpRequest` and `BaseballApiError` never shows the API key, and `BaseballApiError` can be pickled.
- The underlying exception is available as `err.__cause__` (TypeScript: `err.cause`).

## Example

[examples/dashboard](examples/dashboard) is a runnable standard-library server plus browser dashboard that exercises every SDK method. See its README for setup.

## Development

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest            # tests
.venv/bin/mypy              # strict type checking
.venv/bin/ruff check .      # lint
.venv/bin/ruff format --check .
```

### Live tests

[tests/test_live.py](tests/test_live.py) calls every SDK method against the real API and validates each response against the SDK's types. It is skipped unless `APIBASEBALL_KEY` is set, either in the environment or in a `.env` file (see [.env.example](.env.example); `.env` is git-ignored).

```bash
APIBASEBALL_KEY=your-api-key .venv/bin/pytest -m live -v
```

## License

MIT
