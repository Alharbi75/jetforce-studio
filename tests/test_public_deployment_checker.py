"""Offline tests for the anonymous public-deployment assurance checker."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from scripts.check_public_deployment import (
    anonymous_probe_url,
    check_deployment,
    health_url_for,
    main,
)

RouteResponse = tuple[int, Mapping[str, str], bytes]
Route = RouteResponse | Callable[[BaseHTTPRequestHandler], RouteResponse]


@contextmanager
def local_http_server(routes: Mapping[str, Route]) -> Iterator[str]:
    """Serve deterministic local routes without using the external network."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            route = routes.get(self.path, (404, {}, b"not found"))
            if callable(route):
                route = route(self)
            status, headers, body = route
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_public_redirect_chain_and_healthy_streamlit_endpoint_pass() -> None:
    routes = {
        "/public": (302, {"Location": "/app"}, b""),
        "/app": (200, {}, b"JetForce Studio"),
        "/_stcore/health": (200, {"Content-Type": "text/plain"}, b"ok"),
    }
    with local_http_server(routes) as origin:
        report = check_deployment(f"{origin}/public", timeout=2)

    assert report.passed
    assert report.page.status == 200
    assert report.page.final_url == f"{origin}/app"
    assert [(hop.status, hop.source_url, hop.target_url) for hop in report.page.redirects] == [
        (302, f"{origin}/public", f"{origin}/app")
    ]
    assert report.health.status == 200
    assert report.health.body_preview == "ok"


def test_authentication_redirect_fails_even_when_health_is_available() -> None:
    routes = {
        "/private": (302, {"Location": "/auth/login?payload=private-token"}, b""),
        "/auth/login?payload=private-token": (200, {}, b"Sign in to continue"),
        "/_stcore/health": (200, {}, b"ok"),
    }
    with local_http_server(routes) as origin:
        report = check_deployment(f"{origin}/private", timeout=2)

    assert not report.passed
    assert report.page.final_url == f"{origin}/auth/login?payload=private-token"
    assert any("authentication route" in failure for failure in report.failures)


def test_fresh_ephemeral_cookie_is_shared_with_health_request() -> None:
    def app_route(request: BaseHTTPRequestHandler) -> RouteResponse:
        if "jf_anonymous=ready" in request.headers.get("Cookie", ""):
            return 200, {}, b"JetForce Studio"
        return 303, {"Location": "/anonymous-bootstrap"}, b""

    def bootstrap_route(_request: BaseHTTPRequestHandler) -> RouteResponse:
        return (
            303,
            {
                "Location": "/app",
                "Set-Cookie": "jf_anonymous=ready; Path=/; HttpOnly; SameSite=Lax",
            },
            b"",
        )

    def health_route(request: BaseHTTPRequestHandler) -> RouteResponse:
        if "jf_anonymous=ready" in request.headers.get("Cookie", ""):
            return 200, {}, b"ok"
        return 403, {}, b"authentication required"

    routes: dict[str, Route] = {
        "/app": app_route,
        "/anonymous-bootstrap": bootstrap_route,
        "/_stcore/health": health_route,
    }
    with local_http_server(routes) as origin:
        report = check_deployment(f"{origin}/app", timeout=2)

    assert report.passed
    assert report.page.status == 200
    assert report.page.final_url == f"{origin}/app"
    assert [hop.target_url for hop in report.page.redirects] == [
        f"{origin}/anonymous-bootstrap",
        f"{origin}/app",
    ]
    assert report.health.status == 200


def test_community_probe_preserves_query_and_selects_healthz() -> None:
    public_url = "https://example.streamlit.app/course?mode=basic&embed=false&empty="

    assert anonymous_probe_url(public_url) == (
        "https://example.streamlit.app/course?mode=basic&empty=&embed=true"
    )
    assert health_url_for(public_url) == "https://example.streamlit.app/healthz"
    assert health_url_for("http://127.0.0.1:8501/app") == ("http://127.0.0.1:8501/_stcore/health")


def test_explicit_embed_probe_still_fails_authentication_redirect() -> None:
    routes = {
        "/app?mode=course&embed=true": (302, {"Location": "/auth/app/private"}, b""),
        "/auth/app/private": (200, {}, b"Authentication required"),
        "/_stcore/health": (200, {}, b"ok"),
    }
    with local_http_server(routes) as origin:
        report = check_deployment(f"{origin}/app?mode=course&embed=true", timeout=2)

    assert not report.passed
    assert report.public_url == f"{origin}/app?mode=course&embed=true"
    assert any("authentication route" in failure for failure in report.failures)


def test_health_redirect_to_sign_in_fails_public_assurance() -> None:
    routes = {
        "/app": (200, {}, b"JetForce Studio"),
        "/_stcore/health": (302, {"Location": "/sign-in"}, b""),
        "/sign-in": (200, {}, b"Authentication required"),
    }
    with local_http_server(routes) as origin:
        report = check_deployment(f"{origin}/app", timeout=2)

    assert not report.passed
    assert report.health.final_url == f"{origin}/sign-in"
    assert len(report.health.redirects) == 1
    assert any("health endpoint" in failure for failure in report.failures)
    assert any("authentication route" in failure for failure in report.failures)


def test_cross_origin_page_redirect_fails_even_when_both_servers_are_healthy() -> None:
    destination_routes = {"/landing": (200, {}, b"Unrelated application")}
    with local_http_server(destination_routes) as destination:
        source_routes = {
            "/app": (302, {"Location": f"{destination}/landing"}, b""),
            "/_stcore/health": (200, {}, b"ok"),
        }
        with local_http_server(source_routes) as source:
            report = check_deployment(f"{source}/app", timeout=2)

    assert not report.passed
    assert report.page.final_url == f"{destination}/landing"
    assert any("different origin" in failure for failure in report.failures)


def test_unhealthy_status_and_body_return_nonzero_cli_result(capsys) -> None:
    routes = {
        "/app": (200, {}, b"JetForce Studio"),
        "/_stcore/health": (503, {}, b"unhealthy"),
    }
    with local_http_server(routes) as origin:
        exit_code = main([f"{origin}/app", "--timeout", "2"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "CHECKED_AT_UTC=" in output
    assert "PAGE_STATUS=200" in output
    assert f"FINAL_URL={origin}/app" in output
    assert "PAGE_REDIRECT_COUNT=0" in output
    assert "HEALTH_STATUS=503" in output
    assert "RESULT=FAIL" in output
    assert "FAILURE=health endpoint returned status 503" in output


def test_cli_redacts_auth_payload_from_recorded_redirect_chain(capsys) -> None:
    routes = {
        "/": (302, {"Location": "/auth/login?payload=secret-value"}, b""),
        "/auth/login?payload=secret-value": (200, {}, b"Sign in to continue"),
        "/_stcore/health": (200, {}, b"ok"),
    }
    with local_http_server(routes) as origin:
        exit_code = main([origin, "--timeout", "2"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "secret-value" not in output
    assert "payload=REDACTED" in output


def test_successful_cli_output_records_status_final_url_and_redirects(capsys) -> None:
    routes = {
        "/": (301, {"Location": "/app"}, b""),
        "/app": (200, {}, b"JetForce Studio"),
        "/_stcore/health": (200, {}, b'{"status":"ok"}'),
    }
    with local_http_server(routes) as origin:
        exit_code = main([origin, "--timeout", "2"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "PAGE_STATUS=200" in output
    assert f"FINAL_URL={origin}/app" in output
    assert "PAGE_REDIRECT_COUNT=1" in output
    assert f"PAGE_REDIRECT_1=301|{origin}/|{origin}/app" in output
    assert "HEALTH_STATUS=200" in output
    assert "RESULT=PASS" in output
