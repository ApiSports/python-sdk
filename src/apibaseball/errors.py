"""Exceptions raised by the SDK."""

from typing import Any


class BaseballApiError(Exception):
    """Raised when an API request fails.

    This covers HTTP status ``>= 400``, a non-success response envelope, a
    timeout or network failure, and a response body that is not a JSON object.
    The underlying exception, if any, is chained as ``__cause__``.

    Attributes:
        message: Human-readable error message.
        status: HTTP status code (``0`` when the request never completed,
            e.g. on timeout or network failure).
        code: API error code from the response body, when present.
        body: Raw response body when available (decoded JSON or text).
    """

    message: str
    status: int
    code: str | int | float | None
    body: Any

    def __init__(
        self,
        message: str,
        *,
        status: int,
        code: str | int | float | None = None,
        body: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.body = body

    def __reduce__(self) -> tuple[Any, ...]:
        # Keyword-only fields need an explicit recipe for pickle/copy.
        return (_rebuild, (type(self), self.message, self.status, self.code, self.body))

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(message={self.message!r}, "
            f"status={self.status!r}, code={self.code!r})"
        )


def _rebuild(
    cls: type[BaseballApiError],
    message: str,
    status: int,
    code: str | int | float | None,
    body: Any,
) -> BaseballApiError:
    return cls(message, status=status, code=code, body=body)
