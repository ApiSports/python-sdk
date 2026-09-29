"""HTTP layer: URL/query building, transport, and response-envelope parsing.

The default transport uses only the standard library (:mod:`urllib.request`),
so the SDK has no runtime dependencies.
"""

import http.client
import json
import math
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, NoReturn, TypeVar
from urllib.parse import quote_plus

from ._version import __version__ as _version
from .errors import BaseballApiError
from .types.common import ApiResponse, Paginated

T = TypeVar("T")

DEFAULT_BASE_URL = "https://api.api-baseball.com/api"
"""Base URL used when none is configured."""

AuthIn = Literal["header", "query"]
"""Where to send the API key: ``X-Api-Key`` header or ``api_key`` query param."""

QueryValue = str | int | float | bool | date | None
QueryParams = Mapping[str, QueryValue]


@dataclass(frozen=True)
class HttpRequest:
    """A request handed to a :data:`Transport`."""

    method: str
    url: str
    headers: Mapping[str, str]
    timeout: float | None
    """Timeout in seconds, or ``None`` for no timeout."""

    def __repr__(self) -> str:
        # Mask the API key so requests can be logged safely.
        headers = {
            key: "***" if key.lower() == "x-api-key" else value
            for key, value in self.headers.items()
        }
        url = re.sub(r"([?&]api_key=)[^&#]*", r"\1***", self.url)
        return (
            f"HttpRequest(method={self.method!r}, url={url!r}, "
            f"headers={headers!r}, timeout={self.timeout!r})"
        )


@dataclass(frozen=True)
class HttpResponse:
    """A response returned by a :data:`Transport`."""

    status: int
    body: str
    """Response body decoded as text (empty string when there is no body)."""


Transport = Callable[[HttpRequest], HttpResponse]
"""Performs an HTTP request.

A transport must return an :class:`HttpResponse` for every HTTP status
(including 4xx/5xx), raise :class:`TimeoutError` when the request times out,
and raise another :class:`OSError` for network failures.
"""


_USER_AGENT = f"apibaseball-python/{_version}"


def urllib_transport(request: HttpRequest) -> HttpResponse:
    """Default :data:`Transport`, built on :func:`urllib.request.urlopen`."""
    headers = {"User-Agent": _USER_AGENT, **request.headers}
    try:
        req = urllib.request.Request(
            request.url, headers=headers, method=request.method
        )
        if request.timeout is None:
            resp = urllib.request.urlopen(req)
        else:
            resp = urllib.request.urlopen(req, timeout=request.timeout)
        with resp:
            return HttpResponse(status=resp.status, body=_decode(resp.read()))
    except urllib.error.HTTPError as err:
        # urllib raises for 4xx/5xx; the SDK wants the response itself.
        with err:
            return HttpResponse(status=err.code, body=_decode(err.read()))
    except urllib.error.URLError as err:
        if isinstance(err.reason, TimeoutError):
            raise TimeoutError(str(err.reason)) from err
        raise
    except (http.client.HTTPException, ValueError) as err:
        # Malformed URLs/headers and protocol errors (e.g. BadStatusLine) are not
        # OSErrors; surface them as network failures, as `fetch` would.
        raise ConnectionError(str(err) or type(err).__name__) from err


def _decode(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


@dataclass(frozen=True)
class HttpClientConfig:
    """Resolved client configuration shared by every request."""

    api_key: str = field(repr=False)
    base_url: str = DEFAULT_BASE_URL
    auth_in: AuthIn = "header"
    transport: Transport = urllib_transport
    timeout: float | None = None
    """Timeout in seconds; ``None`` or ``0`` disables it."""


def format_value(value: str | int | float | bool | date) -> str:
    # Mirror JavaScript's String(value) so both SDKs send identical queries.
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, date):
        return f"{value.year:04d}-{value.month:02d}-{value.day:02d}"
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return str(int(value))
    return str(value)


def _quote(value: str) -> str:
    # Match URLSearchParams encoding: "*" is left as-is and "~" is escaped.
    return quote_plus(value, safe="*").replace("~", "%7E")


def build_query(params: QueryParams | None = None) -> str:
    """Serialize query params into ``?a=1&b=2``, omitting ``None`` values."""
    if not params:
        return ""
    qs = "&".join(
        f"{_quote(key)}={_quote(format_value(value))}"
        for key, value in params.items()
        if value is not None
    )
    return f"?{qs}" if qs else ""


def join_url(base_url: str, path: str) -> str:
    """Join ``base_url`` and ``path`` with exactly one slash between them."""
    base = base_url.rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base}{suffix}"


def _reject_constant(name: str) -> NoReturn:
    # JSON.parse rejects NaN/Infinity; json.loads accepts them by default.
    raise ValueError(f"Invalid JSON constant: {name}")


def _read_body(text: str) -> Any:
    """Decode JSON, fall back to raw text, or ``None`` for an empty body."""
    # Response.text() in JavaScript drops a leading byte-order mark.
    text = text.removeprefix("\ufeff")
    if not text:
        return None
    try:
        return json.loads(text, parse_constant=_reject_constant)
    except ValueError:
        return text


def _extract_error_message(body: Any, fallback: str) -> str:
    if isinstance(body, str) and body.strip():
        return body
    if isinstance(body, dict):
        for key in ("message", "error", "error_message", "detail"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return fallback


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _extract_error_code(body: Any) -> str | int | float | None:
    if not isinstance(body, dict):
        return None
    code = body.get("code")
    if code is None:
        code = body.get("error_code")
    if isinstance(code, str | int | float) and not isinstance(code, bool):
        return code
    return None


def _js_string(envelope: Mapping[str, Any], key: str) -> str:
    """Render ``envelope[key]`` the way JavaScript's ``String()`` would."""
    if key not in envelope:
        return "undefined"
    value = envelope[key]
    if value is None:
        return "null"
    return _js_value_string(value)


def _js_value_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str | int | float | bool):
        return format_value(value)
    if isinstance(value, list):
        return ",".join(_js_value_string(item) for item in value)
    return "[object Object]"


def _is_falsy(value: Any) -> bool:
    """JavaScript truthiness: only null, false, 0 and "" count as falsy here."""
    return (
        value is None
        or value is False
        or value == ""
        or (_is_number(value) and value == 0)
    )


def _redact(text: str, api_key: str) -> str:
    """Mask the API key in ``text``.

    ``api_key=<value>`` query pairs are always masked; the bare key only when it
    is long enough not to mangle ordinary words.
    """
    forms = {api_key, _quote(api_key), api_key.strip()}
    for form in forms:
        if form:
            text = text.replace(f"api_key={form}", "api_key=***")
    for form in forms:
        if len(form) >= 8:
            text = text.replace(form, "***")
    return text


def _network_error(error: OSError, api_key: str) -> BaseballApiError:
    if isinstance(error, urllib.error.URLError):
        message = str(error.reason)
    else:
        message = str(error)
    return BaseballApiError(
        _redact(message, api_key) or "Network request failed", status=0
    )


def _leaks(error: BaseException, api_key: str) -> bool:
    """Whether ``error`` or anything it chains mentions the API key."""
    seen: BaseException | None = error
    while seen is not None:
        if _redact(str(seen), api_key) != str(seen):
            return True
        seen = seen.__cause__ or seen.__context__
    return False


def request(
    config: HttpClientConfig,
    path: str,
    query: QueryParams | None = None,
) -> ApiResponse[Any]:
    """Perform an authenticated GET and unwrap the API envelope.

    Raises:
        BaseballApiError: On HTTP status ``>= 400``, a non-success envelope,
            a timeout or network failure, or a body that is not a JSON object.
    """
    params: dict[str, QueryValue] = dict(query or {})
    headers = {"Accept": "application/json"}

    if config.auth_in == "header":
        headers["X-Api-Key"] = config.api_key
    else:
        params["api_key"] = config.api_key

    url = f"{join_url(config.base_url, path)}{build_query(params)}"
    timeout = (
        config.timeout if config.timeout and 0 < config.timeout < math.inf else None
    )

    try:
        response = config.transport(
            HttpRequest(method="GET", url=url, headers=headers, timeout=timeout)
        )
    except OSError as err:
        if isinstance(err, TimeoutError) and timeout is not None:
            error = BaseballApiError(
                f"Request timed out after {format_value(timeout)}s", status=0
            )
        else:
            error = _network_error(err, config.api_key)
        # Keep the cause for debugging unless its traceback would print the key.
        raise error from (None if _leaks(err, config.api_key) else err)

    body = _read_body(response.body)

    if response.status >= 400:
        raise BaseballApiError(
            _extract_error_message(body, f"HTTP {response.status}"),
            status=response.status,
            code=_extract_error_code(body),
            body=body,
        )

    # A JSON object is expected; like the TypeScript SDK, a JSON array gets
    # past this check and then fails the success check below.
    if not isinstance(body, dict | list):
        raise BaseballApiError(
            "Invalid API response: expected a JSON object",
            status=response.status,
            body=body,
        )

    envelope: Mapping[str, Any] = body if isinstance(body, dict) else {}

    # The API is inconsistent about how it signals success. Some endpoints
    # return `success: 1` (or `true`) alongside `result`, while others omit
    # `success` and instead return `message: "Success"` with the payload under
    # `data`.
    has_success_flag = "success" in envelope
    success_flag = envelope.get("success")
    success_by_flag = (
        success_flag is True
        or success_flag == "1"
        or (_is_number(success_flag) and success_flag == 1)
    )
    message = envelope.get("message")
    success_by_message = (
        not has_success_flag
        and isinstance(message, str)
        and message.lower() == "success"
    )

    if not success_by_flag and not success_by_message:
        code = _extract_error_code(body)
        if code is None and isinstance(success_flag, str | int | float):
            code = success_flag
        raise BaseballApiError(
            _extract_error_message(
                body,
                f"API request failed with success={_js_string(envelope, 'success')}",
            ),
            status=response.status,
            code=code,
            body=body,
        )

    # Prefer `result` when present, otherwise fall back to `data` (used by the
    # `message: "Success"` style responses).
    result = envelope["result"] if "result" in envelope else envelope.get("data")

    api_response: ApiResponse[Any] = {"success": 1, "result": result}
    if "pagination" in envelope:
        api_response["pagination"] = envelope["pagination"]
    return api_response


def as_paginated(response: ApiResponse[T]) -> Paginated[T]:
    """Return ``result`` + ``pagination`` for paginated endpoints.

    Raises:
        BaseballApiError: If the response has no pagination metadata.
    """
    pagination = response.get("pagination")
    if pagination is None or _is_falsy(pagination):
        raise BaseballApiError(
            "Expected pagination metadata in API response",
            status=0,
            body=response,
        )
    return {"result": response["result"], "pagination": pagination}
