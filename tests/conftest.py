import json
from collections.abc import Callable
from typing import Any

import pytest

from apibaseball import BaseballClient, HttpRequest, HttpResponse, Pagination

API_KEY = "test-api-key"

PAGINATION: Pagination = {
    "current_page": 1,
    "per_page": 15,
    "total": 1,
    "last_page": 1,
    "from": 1,
    "to": 1,
}


class FakeTransport:
    """Records requests and replies with a canned response (or raises)."""

    def __init__(self) -> None:
        self.requests: list[HttpRequest] = []
        self.status = 200
        self.body = ""
        self.error: BaseException | None = None

    def reply(self, body: Any, status: int = 200) -> "FakeTransport":
        self.body = body if isinstance(body, str) else json.dumps(body)
        self.status = status
        return self

    def raise_(self, error: BaseException) -> "FakeTransport":
        self.error = error
        return self

    @property
    def last(self) -> HttpRequest:
        assert self.requests, "no request was made"
        return self.requests[-1]

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return HttpResponse(status=self.status, body=self.body)


@pytest.fixture
def transport() -> FakeTransport:
    return FakeTransport()


MakeClient = Callable[..., BaseballClient]


@pytest.fixture
def make_client(transport: FakeTransport) -> MakeClient:
    def factory(**overrides: Any) -> BaseballClient:
        return BaseballClient(API_KEY, transport=transport, **overrides)

    return factory
