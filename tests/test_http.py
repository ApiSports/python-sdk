"""HTTP-layer tests: query building, envelope parsing, and error mapping."""

import copy
import pickle
import urllib.error
from datetime import date
from typing import Any

import pytest
from conftest import API_KEY, FakeTransport, MakeClient

from apibaseball import BaseballApiError, BaseballClient
from apibaseball._http import build_query, join_url

# --- query building ---------------------------------------------------------


def test_build_query_empty() -> None:
    assert build_query() == ""
    assert build_query({}) == ""
    assert build_query({"a": None}) == ""


def test_build_query_omits_none_and_keeps_order() -> None:
    assert build_query({"b": 2, "a": None, "c": "x"}) == "?b=2&c=x"


def test_build_query_serializes_like_javascript_string() -> None:
    assert build_query({"t": True, "f": False, "n": 0, "fl": 2.0, "x": 1.5}) == (
        "?t=true&f=false&n=0&fl=2&x=1.5"
    )


def test_build_query_keeps_empty_strings() -> None:
    assert build_query({"q": ""}) == "?q="


def test_build_query_encodes_like_url_search_params() -> None:
    assert build_query({"q": "a b&c=d/*~é"}) == "?q=a+b%26c%3Dd%2F*%7E%C3%A9"


@pytest.mark.parametrize(
    ("base", "path", "expected"),
    [
        ("https://x.test/api", "/a", "https://x.test/api/a"),
        ("https://x.test/api/", "/a", "https://x.test/api/a"),
        ("https://x.test/api//", "a", "https://x.test/api/a"),
    ],
)
def test_join_url(base: str, path: str, expected: str) -> None:
    assert join_url(base, path) == expected


# --- HTTP errors ------------------------------------------------------------


def fetch_error(make_client: MakeClient, **overrides: Any) -> BaseballApiError:
    with pytest.raises(BaseballApiError) as info:
        make_client(**overrides).get_countries()
    return info.value


def test_raises_on_http_error_with_message_and_code(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    body = {"message": "Unauthorized", "code": "auth_error"}
    transport.reply(body, status=401)

    error = fetch_error(make_client)

    assert error.message == "Unauthorized"
    assert str(error) == "Unauthorized"
    assert error.status == 401
    assert error.code == "auth_error"
    assert error.body == body


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"error": "Bad thing"}, "Bad thing"),
        ({"error_message": "Worse thing"}, "Worse thing"),
        ({"detail": "Detail thing"}, "Detail thing"),
        ({"message": "  ", "detail": "Fallback key"}, "Fallback key"),
        ({"message": 123}, "HTTP 500"),
        ({}, "HTTP 500"),
    ],
)
def test_http_error_message_extraction(
    transport: FakeTransport,
    make_client: MakeClient,
    body: dict[str, Any],
    message: str,
) -> None:
    transport.reply(body, status=500)

    assert fetch_error(make_client).message == message


def test_http_error_with_text_body_uses_text(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply("Service Unavailable", status=503)

    error = fetch_error(make_client)

    assert error.message == "Service Unavailable"
    assert error.body == "Service Unavailable"
    assert error.code is None


@pytest.mark.parametrize("text", ["", "   "])
def test_http_error_with_empty_body_uses_status(
    transport: FakeTransport, make_client: MakeClient, text: str
) -> None:
    transport.reply(text, status=502)

    error = fetch_error(make_client)

    assert error.message == "HTTP 502"
    assert error.status == 502


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"error_code": 42}, 42),
        ({"code": None, "error_code": "E1"}, "E1"),
        ({"code": 7, "error_code": "E1"}, 7),
        ({"code": True}, None),
        ({"code": {"nested": 1}}, None),
    ],
)
def test_http_error_code_extraction(
    transport: FakeTransport,
    make_client: MakeClient,
    body: dict[str, Any],
    code: object,
) -> None:
    transport.reply(body, status=400)

    assert fetch_error(make_client).code == code


# --- envelope parsing -------------------------------------------------------


def test_raises_when_success_is_not_1(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    body = {"success": 0, "message": "Invalid date range", "result": None}
    transport.reply(body)

    with pytest.raises(BaseballApiError) as info:
        make_client().get_odds(from_="2026-07-01", to="2026-07-10")

    assert info.value.message == "Invalid date range"
    assert info.value.status == 200
    assert info.value.code == 0
    assert info.value.body == body


def test_success_failure_prefers_body_code_over_flag(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 0, "code": "rate_limited"})

    assert fetch_error(make_client).code == "rate_limited"


@pytest.mark.parametrize("flag", [1, True, "1", 1.0])
def test_accepts_success_flag_variants(
    transport: FakeTransport, make_client: MakeClient, flag: object
) -> None:
    transport.reply({"success": flag, "result": ["ok"]})

    result: object = make_client().get_countries()
    assert result == ["ok"]


@pytest.mark.parametrize(
    ("flag", "rendered"),
    [(0, "0"), (False, "false"), ("true", "true"), (2, "2"), (None, "null")],
)
def test_rejects_other_success_flags(
    transport: FakeTransport, make_client: MakeClient, flag: object, rendered: str
) -> None:
    transport.reply({"success": flag, "result": ["ok"]})

    error = fetch_error(make_client)

    assert error.message == f"API request failed with success={rendered}"
    assert error.code == flag


def test_missing_success_and_message_fails(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"result": []})

    error = fetch_error(make_client)

    assert error.message == "API request failed with success=undefined"
    assert error.code is None


@pytest.mark.parametrize("message", ["Success", "success", "SUCCESS"])
def test_message_success_style_uses_data(
    transport: FakeTransport, make_client: MakeClient, message: str
) -> None:
    transport.reply({"message": message, "data": [{"id": 1}]})

    result: object = make_client().get_countries()
    assert result == [{"id": 1}]


def test_message_success_ignored_when_success_flag_present(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 0, "message": "Success", "data": []})

    assert fetch_error(make_client).message == "Success"


def test_result_is_preferred_over_data(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": ["r"], "data": ["d"]})

    result: object = make_client().get_countries()
    assert result == ["r"]


def test_explicit_null_result_is_not_replaced_by_data(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": None, "data": ["d"]})

    assert make_client().get_countries() is None


def test_missing_result_and_data_returns_none(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1})

    assert make_client().get_countries() is None


# --- malformed responses ----------------------------------------------------


@pytest.mark.parametrize(
    ("text", "body"),
    [
        ("<html>oops</html>", "<html>oops</html>"),
        ("", None),
        ("null", None),
        ("42", 42),
        ('"text"', "text"),
        ("true", True),
        ("NaN", "NaN"),
    ],
)
def test_non_object_body_is_invalid(
    transport: FakeTransport, make_client: MakeClient, text: str, body: object
) -> None:
    transport.reply(text)

    error = fetch_error(make_client)

    assert error.message == "Invalid API response: expected a JSON object"
    assert error.status == 200
    assert error.body == body


def test_array_body_fails_success_check(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply([1, 2])

    error = fetch_error(make_client)

    assert error.message == "API request failed with success=undefined"
    assert error.body == [1, 2]


def test_empty_object_body_fails_success_check(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({})

    assert fetch_error(make_client).message == (
        "API request failed with success=undefined"
    )


# --- transport failures -----------------------------------------------------


def test_timeout_raises_with_status_0(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    cause = TimeoutError("timed out")
    transport.raise_(cause)

    error = fetch_error(make_client, timeout=5)

    assert error.message == "Request timed out after 5s"
    assert error.status == 0
    assert error.__cause__ is cause


def test_fractional_timeout_message(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.raise_(TimeoutError())

    assert fetch_error(make_client, timeout=0.25).message == (
        "Request timed out after 0.25s"
    )


def test_timeout_error_without_configured_timeout_is_a_network_error(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.raise_(TimeoutError("socket stalled"))

    error = fetch_error(make_client)

    assert error.message == "socket stalled"
    assert error.status == 0


def test_network_error_raises_with_status_0(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    cause = urllib.error.URLError("nodename nor servname provided")
    transport.raise_(cause)

    error = fetch_error(make_client)

    assert error.message == "nodename nor servname provided"
    assert error.status == 0
    assert error.code is None
    assert error.body is None
    assert error.__cause__ is cause


def test_network_error_without_message_uses_fallback(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.raise_(ConnectionResetError())

    assert fetch_error(make_client).message == "Network request failed"


def test_network_error_message_redacts_api_key(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.raise_(OSError(f"cannot reach https://x.test/?api_key={API_KEY}"))

    error = fetch_error(make_client, auth_in="query")

    assert API_KEY not in error.message
    assert error.message == "cannot reach https://x.test/?api_key=***"


def test_non_network_transport_errors_propagate(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.raise_(RuntimeError("bug in custom transport"))

    with pytest.raises(RuntimeError, match="bug in custom transport"):
        make_client().get_countries()


def test_error_repr_is_concise_and_safe(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"message": "Unauthorized", "code": "auth_error"}, status=401)

    error = fetch_error(make_client)

    assert repr(error) == (
        "BaseballApiError(message='Unauthorized', status=401, code='auth_error')"
    )
    assert API_KEY not in repr(error)
    assert isinstance(error, Exception)


# --- review follow-ups ------------------------------------------------------


def test_leading_bom_is_ignored(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply('﻿{"success": 1, "result": [5]}')

    result: object = make_client().get_countries()

    assert result == [5]


def test_bom_only_error_body_uses_status(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply("﻿", status=500)

    assert fetch_error(make_client).message == "HTTP 500"


@pytest.mark.parametrize(
    ("flag", "rendered", "code"),
    [({"a": 1}, "[object Object]", None), ([0, None], "0,", None)],
)
def test_structured_success_flags_render_like_javascript(
    transport: FakeTransport,
    make_client: MakeClient,
    flag: object,
    rendered: str,
    code: object,
) -> None:
    transport.reply({"success": flag})

    error = fetch_error(make_client)

    assert error.message == f"API request failed with success={rendered}"
    assert error.code == code


def test_path_params_are_formatted_like_javascript(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": {}})

    make_client().get_team_stats(5.0)  # type: ignore[arg-type]

    assert transport.last.url.endswith("/baseball/teams/5/stats")


def test_large_timeout_message_keeps_precision(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.raise_(TimeoutError())

    assert fetch_error(make_client, timeout=1234.5678).message == (
        "Request timed out after 1234.5678s"
    )


def test_redaction_only_targets_the_api_key_query_value(
    transport: FakeTransport,
) -> None:
    transport.raise_(OSError("unknown url type: k?api_key=k"))
    client = BaseballClient("k", transport=transport, auth_in="query")

    with pytest.raises(BaseballApiError) as info:
        client.get_countries()

    assert info.value.message == "unknown url type: k?api_key=***"


def test_redaction_handles_url_encoded_keys(transport: FakeTransport) -> None:
    transport.raise_(OSError("failed: https://x.test/?api_key=a+b%2Fc"))
    client = BaseballClient("a b/c", transport=transport, auth_in="query")

    with pytest.raises(BaseballApiError) as info:
        client.get_countries()

    assert info.value.message == "failed: https://x.test/?api_key=***"


def test_dates_are_zero_padded() -> None:
    assert build_query({"from": date(999, 1, 2)}) == "?from=0999-01-02"


@pytest.mark.parametrize("pagination", [0, False, ""])
def test_falsy_pagination_raises(
    transport: FakeTransport, make_client: MakeClient, pagination: object
) -> None:
    transport.reply({"success": 1, "result": [], "pagination": pagination})

    with pytest.raises(BaseballApiError, match="Expected pagination metadata"):
        make_client().get_leagues()


@pytest.mark.parametrize("pagination", [{}, []])
def test_truthy_empty_pagination_passes_through(
    transport: FakeTransport, make_client: MakeClient, pagination: object
) -> None:
    transport.reply({"success": 1, "result": [], "pagination": pagination})

    page: object = make_client().get_leagues()

    assert page == {"result": [], "pagination": pagination}


def test_cause_is_dropped_when_it_would_leak_the_key(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.raise_(OSError(f"cannot reach https://x.test/?api_key={API_KEY}"))

    error = fetch_error(make_client, auth_in="query")

    assert error.__cause__ is None
    assert error.__suppress_context__


def test_bare_long_key_is_redacted(transport: FakeTransport) -> None:
    transport.raise_(OSError("Invalid header value b'SECRETKEY\\n'"))
    client = BaseballClient("SECRETKEY\n", transport=transport)

    with pytest.raises(BaseballApiError) as info:
        client.get_countries()

    assert "SECRETKEY" not in info.value.message


@pytest.mark.parametrize("timeout", [float("inf"), float("nan")])
def test_non_finite_timeout_disables_timeout(
    transport: FakeTransport, make_client: MakeClient, timeout: float
) -> None:
    transport.reply({"success": 1, "result": []})

    make_client(timeout=timeout).get_countries()

    assert transport.last.timeout is None


def test_http_request_repr_masks_api_key(
    transport: FakeTransport, make_client: MakeClient
) -> None:
    transport.reply({"success": 1, "result": []})
    make_client().get_countries()
    make_client(auth_in="query").get_players(team_id=1)

    header_repr, query_repr = (repr(r) for r in transport.requests)

    assert API_KEY not in header_repr
    assert "'X-Api-Key': '***'" in header_repr
    assert API_KEY not in query_repr
    assert "team_id=1&api_key=***" in query_repr


def test_error_survives_pickle_and_copy() -> None:
    error = BaseballApiError("boom", status=401, code="auth", body={"a": 1})

    for clone in (
        pickle.loads(pickle.dumps(error)),
        copy.copy(error),
        copy.deepcopy(error),
    ):
        assert type(clone) is BaseballApiError
        assert (clone.message, clone.status, clone.code, clone.body) == (
            "boom",
            401,
            "auth",
            {"a": 1},
        )
