"""Shared API envelope, pagination and reference-data shapes.

Every model is a :class:`~typing.TypedDict`: the SDK returns the JSON decoded
from the API as plain ``dict``/``list`` values (no runtime conversion), and
these types describe that shape for type checkers and IDEs.
"""

from typing import Generic, NotRequired, TypedDict, TypeVar

T = TypeVar("T")

# ``from`` is a Python keyword, so this TypedDict uses the functional syntax.
Pagination = TypedDict(
    "Pagination",
    {
        "current_page": int,
        "per_page": int,
        "total": int,
        "last_page": int,
        "from": int | None,
        "to": int | None,
    },
)
Pagination.__doc__ = "Pagination metadata returned by list endpoints."


class ApiResponse(TypedDict, Generic[T]):
    """Uniform API envelope: ``{"success", "result", "pagination"?}``."""

    success: int
    result: T
    pagination: NotRequired[Pagination]


class Paginated(TypedDict, Generic[T]):
    """Convenience shape returned by paginated endpoints."""

    result: T
    pagination: Pagination


class Country(TypedDict):
    """Country from ``/baseball/countries``."""

    id: int
    name: str
    logo: str | None


class League(TypedDict):
    """League from ``/baseball/leagues`` and ``/baseball/countries/{id}/leagues``."""

    id: int
    name: str
    country: str | None
    year: str | None
    country_id: int
    logo: str | None
    country_logo: str | None
    importance: int | None
    date_start: str | None
    date_stop: str | None


class Team(TypedDict):
    """Team from ``/baseball/leagues/{id}/teams``."""

    id: int
    name: str
    slug: str | None
    logo: str | None
    active: bool
    venue_name: str | None
    venue_city: str | None
    venue_capacity: int | None


class Player(TypedDict):
    """Generic player profile (shared schema).

    Prefer :class:`~apibaseball.BaseballPlayer` for baseball endpoints.
    """

    player_id: int
    full_name: str
    image: str | None
    age: int | None
    birthdate: str | None
    nationality: str | None
    height: str | None
    weight: str | None
    position: str | None


class Venue(TypedDict):
    """Venue (shared schema)."""

    venue_id: int
    name: str
    city: str | None
    address: str | None
    capacity: int | None
    surface: str | None
