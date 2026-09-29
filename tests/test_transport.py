"""Tests for the default urllib transport against a local HTTP server."""

import json
import socket
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest

from apibaseball import BaseballApiError, BaseballClient, HttpRequest, urllib_transport


class Handler(BaseHTTPRequestHandler):
    last_headers: ClassVar[dict[str, str]] = {}
    last_path: ClassVar[str] = ""

    def do_GET(self) -> None:
        Handler.last_headers = dict(self.headers.items())
        Handler.last_path = self.path
        if self.path.startswith("/slow"):
            time.sleep(0.5)
        if self.path.startswith("/missing"):
            self._send(404, json.dumps({"message": "Not found"}))
        else:
            self._send(200, json.dumps({"success": 1, "result": ["ok", "é"]}))

    def _send(self, status: int, text: str) -> None:
        payload = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        pass


class QuietServer(ThreadingHTTPServer):
    def handle_error(self, request: object, client_address: object) -> None:
        pass  # the timeout test closes its socket before the slow reply


@pytest.fixture
def base_url() -> Iterator[str]:
    server = QuietServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def test_returns_status_and_decoded_body(base_url: str) -> None:
    response = urllib_transport(
        HttpRequest(
            method="GET",
            url=f"{base_url}/ok",
            headers={"X-Api-Key": "k"},
            timeout=5,
        )
    )

    assert response.status == 200
    assert json.loads(response.body) == {"success": 1, "result": ["ok", "é"]}
    assert Handler.last_headers["X-Api-Key"] == "k"


def test_returns_http_error_responses_instead_of_raising(base_url: str) -> None:
    response = urllib_transport(
        HttpRequest(method="GET", url=f"{base_url}/missing", headers={}, timeout=None)
    )

    assert response.status == 404
    assert json.loads(response.body) == {"message": "Not found"}


def test_client_end_to_end(base_url: str) -> None:
    client = BaseballClient("secret", base_url=base_url, timeout=5)

    countries: object = client.get_countries()
    assert countries == ["ok", "é"]
    assert Handler.last_path == "/baseball/countries"
    assert Handler.last_headers["X-Api-Key"] == "secret"
    assert Handler.last_headers["Accept"] == "application/json"


def test_client_maps_http_errors(base_url: str) -> None:
    client = BaseballClient("secret", base_url=f"{base_url}/missing")

    with pytest.raises(BaseballApiError) as info:
        client.get_countries()

    assert info.value.status == 404
    assert info.value.message == "Not found"


def test_client_times_out(base_url: str) -> None:
    client = BaseballClient("secret", base_url=f"{base_url}/slow", timeout=0.1)

    with pytest.raises(BaseballApiError) as info:
        client.get_countries()

    assert info.value.message == "Request timed out after 0.1s"
    assert info.value.status == 0
    assert isinstance(info.value.__cause__, TimeoutError)


def test_client_reports_connection_errors() -> None:
    # Port 9 (discard) on localhost is essentially never listening.
    client = BaseballClient("secret", base_url="http://127.0.0.1:9", timeout=2)

    with pytest.raises(BaseballApiError) as info:
        client.get_countries()

    assert info.value.status == 0
    assert info.value.message


def test_client_wraps_invalid_base_url() -> None:
    client = BaseballClient("secret", base_url="api.example.com")

    with pytest.raises(BaseballApiError) as info:
        client.get_countries()

    assert info.value.status == 0
    assert "unknown url type" in info.value.message
    assert isinstance(info.value.__cause__, ConnectionError)


def test_client_wraps_non_latin1_api_key(base_url: str) -> None:
    client = BaseballClient("ключ", base_url=base_url)

    with pytest.raises(BaseballApiError) as info:
        client.get_countries()

    assert info.value.status == 0


def test_sends_user_agent(base_url: str) -> None:
    BaseballClient("secret", base_url=base_url).get_countries()

    assert Handler.last_headers["User-Agent"].startswith("apibaseball-python/")


@pytest.fixture
def garbage_server() -> Iterator[str]:
    """A raw socket server that answers with an invalid HTTP status line."""
    sock = socket.create_server(("127.0.0.1", 0))

    def serve() -> None:
        conn, _ = sock.accept()
        with conn:
            conn.recv(65536)
            conn.sendall(b"garbage\r\n\r\n")

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{sock.getsockname()[1]}"
    finally:
        sock.close()


def test_client_wraps_protocol_errors(garbage_server: str) -> None:
    client = BaseballClient("secret", base_url=garbage_server, timeout=5)

    with pytest.raises(BaseballApiError) as info:
        client.get_countries()

    assert info.value.status == 0
    assert isinstance(info.value.__cause__, ConnectionError)
