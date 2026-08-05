#!/usr/bin/env python3
"""Verify anonymous HTTP access and health for a deployed Streamlit app.

This checker intentionally uses no credentials, persisted browser session, or
third-party package. It permits only fresh, in-memory cookies created during a
single anonymous check. It verifies transport-level public reachability; it
does not replace the signed-out browser and physical-device checks in
DEPLOYMENT.md.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import Message
from http.client import HTTPMessage
from typing import Any

USER_AGENT = "JetForce-Public-Deployment-Checker/1.0"
MAX_BODY_BYTES = 4096
AUTH_HOST_LABELS = frozenset({"account", "accounts", "auth", "login", "signin", "sso"})
AUTH_PATH_TOKENS = frozenset(
    {
        "auth",
        "authenticate",
        "authentication",
        "authorize",
        "login",
        "log-in",
        "oauth",
        "oauth2",
        "sign-in",
        "signin",
        "sso",
    }
)
AUTH_BODY_MARKERS = (
    "authentication required",
    "log in to continue",
    "login required",
    "request access",
    "sign in to continue",
    "this app is private",
)
SENSITIVE_QUERY_KEYS = frozenset(
    {
        "access_token",
        "code",
        "id_token",
        "key",
        "password",
        "payload",
        "secret",
        "sig",
        "state",
        "token",
    }
)


@dataclass(frozen=True, slots=True)
class RedirectHop:
    """One HTTP redirect followed by the anonymous client."""

    status: int
    source_url: str
    target_url: str


@dataclass(frozen=True, slots=True)
class HttpObservation:
    """Result of one bounded anonymous GET request."""

    requested_url: str
    status: int | None
    final_url: str
    redirects: tuple[RedirectHop, ...]
    body_preview: str
    error: str | None = None


@dataclass(frozen=True, slots=True)
class DeploymentReport:
    """Combined public-page and Streamlit-health observations."""

    checked_at_utc: str
    public_url: str
    page: HttpObservation
    health: HttpObservation
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


class RecordingRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow redirects normally while retaining their status and URLs."""

    def __init__(self) -> None:
        super().__init__()
        self.redirects: list[RedirectHop] = []

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        self.redirects.append(RedirectHop(code, req.full_url, newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def normalize_url(raw_url: str) -> str:
    """Validate an anonymous HTTP(S) URL and remove any fragment."""

    candidate = raw_url.strip()
    parsed = urllib.parse.urlsplit(candidate)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("The deployment URL must be an absolute HTTP or HTTPS URL.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("The deployment URL must not contain credentials.")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("The deployment URL contains an invalid port.") from exc
    path = parsed.path or "/"
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc, path, parsed.query, ""))


def _decode_body(payload: bytes, headers: Message[str, str]) -> str:
    charset = headers.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def fetch_anonymous(
    url: str,
    *,
    timeout: float = 15.0,
    cookie_jar: http.cookiejar.CookieJar | None = None,
) -> HttpObservation:
    """Perform one anonymous GET, following and recording redirects.

    The caller may supply a fresh in-memory cookie jar so temporary cookies
    issued by an anonymous Streamlit bootstrap also reach the health request.
    No cookie is loaded from or persisted to disk.
    """

    requested_url = normalize_url(url)
    redirect_handler = RecordingRedirectHandler()
    session_cookies = cookie_jar if cookie_jar is not None else http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(session_cookies), redirect_handler
    )
    request = urllib.request.Request(
        requested_url,
        headers={
            "Accept": "text/html,application/json,text/plain;q=0.9,*/*;q=0.1",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            payload = response.read(MAX_BODY_BYTES)
            return HttpObservation(
                requested_url=requested_url,
                status=int(response.status),
                final_url=response.geturl(),
                redirects=tuple(redirect_handler.redirects),
                body_preview=_decode_body(payload, response.headers),
            )
    except urllib.error.HTTPError as exc:
        payload = exc.read(MAX_BODY_BYTES)
        return HttpObservation(
            requested_url=requested_url,
            status=int(exc.code),
            final_url=exc.geturl(),
            redirects=tuple(redirect_handler.redirects),
            body_preview=_decode_body(payload, exc.headers),
            error=f"HTTP {exc.code}: {exc.reason}",
        )
    except OSError as exc:
        return HttpObservation(
            requested_url=requested_url,
            status=None,
            final_url=requested_url,
            redirects=tuple(redirect_handler.redirects),
            body_preview="",
            error=f"{type(exc).__name__}: {exc}",
        )


def is_auth_url(url: str) -> bool:
    """Return whether a URL visibly points at a sign-in or authorization route."""

    parsed = urllib.parse.urlsplit(url)
    host_labels = set((parsed.hostname or "").lower().split("."))
    if host_labels & AUTH_HOST_LABELS:
        return True
    segments = [urllib.parse.unquote(segment).lower() for segment in parsed.path.split("/")]
    for segment in segments:
        normalized = re.sub(r"[_-]+", "-", segment).strip("-")
        if normalized in AUTH_PATH_TOKENS or normalized.startswith("oauth"):
            return True
    return False


def authentication_failure(observation: HttpObservation) -> str | None:
    """Describe an authentication barrier found in status, routes, or response text."""

    if observation.status in {401, 403}:
        return f"anonymous request returned HTTP {observation.status}"
    if is_auth_url(observation.requested_url):
        return (
            "anonymous request began at authentication route "
            f"{_display_url(observation.requested_url)}"
        )
    if is_auth_url(observation.final_url):
        return (
            "anonymous request stopped at authentication route "
            f"{_display_url(observation.final_url)}"
        )
    for hop in observation.redirects:
        if not is_auth_url(hop.target_url):
            continue
        return "anonymous request reached authentication route " f"{_display_url(hop.target_url)}"
    preview = observation.body_preview.casefold()
    for marker in AUTH_BODY_MARKERS:
        if marker in preview:
            return f"anonymous response contained authentication marker {marker!r}"
    return None


def is_community_cloud_url(url: str) -> bool:
    """Return whether a URL uses Streamlit Community Cloud's public app domain."""

    host = (urllib.parse.urlsplit(url).hostname or "").casefold()
    return host == "streamlit.app" or host.endswith(".streamlit.app")


def anonymous_probe_url(public_url: str) -> str:
    """Return the strict anonymous page probe without changing the reported URL."""

    normalized = normalize_url(public_url)
    if not is_community_cloud_url(normalized):
        return normalized
    parsed = urllib.parse.urlsplit(normalized)
    query = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if key.casefold() != "embed"
    ]
    query.append(("embed", "true"))
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), "")
    )


def health_url_for(public_url: str) -> str:
    """Build the platform-appropriate health URL from the public app origin."""

    normalized = normalize_url(public_url)
    parsed = urllib.parse.urlsplit(normalized)
    health_path = "/healthz" if is_community_cloud_url(normalized) else "/_stcore/health"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, health_path, "", ""))


def _origin(url: str) -> tuple[str, str, int | None]:
    """Return a normalized scheme/host/effective-port origin tuple."""

    parsed = urllib.parse.urlsplit(url)
    scheme = parsed.scheme.casefold()
    default_port = 443 if scheme == "https" else 80 if scheme == "http" else None
    return scheme, (parsed.hostname or "").casefold(), parsed.port or default_port


def _same_origin(first_url: str, second_url: str) -> bool:
    return _origin(first_url) == _origin(second_url)


def _health_body_is_ok(body: str) -> bool:
    normalized = body.strip().casefold()
    if normalized in {"healthy", "ok"}:
        return True
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return False
    return isinstance(payload, dict) and str(payload.get("status", "")).casefold() in {
        "healthy",
        "ok",
    }


def check_deployment(url: str, *, timeout: float = 15.0) -> DeploymentReport:
    """Check a public page and its Streamlit health endpoint without credentials."""

    if timeout <= 0:
        raise ValueError("Timeout must be greater than zero seconds.")
    public_url = normalize_url(url)
    session_cookies = http.cookiejar.CookieJar()
    page = fetch_anonymous(
        anonymous_probe_url(public_url), timeout=timeout, cookie_jar=session_cookies
    )
    health = fetch_anonymous(
        health_url_for(public_url), timeout=timeout, cookie_jar=session_cookies
    )
    failures: list[str] = []

    if page.error and page.status is None:
        failures.append(f"public page request failed: {page.error}")
    elif page.status is None or not 200 <= page.status < 300:
        failures.append(f"public page returned status {page.status}")
    page_auth_failure = authentication_failure(page)
    if page_auth_failure:
        failures.append(page_auth_failure)
    if page.status is not None and not _same_origin(public_url, page.final_url):
        failures.append(
            "public page completed at a different origin " f"{_display_url(page.final_url)}"
        )

    if health.error and health.status is None:
        failures.append(f"health request failed: {health.error}")
    elif health.status is None or not 200 <= health.status < 300:
        failures.append(f"health endpoint returned status {health.status}")
    health_auth_failure = authentication_failure(health)
    if health_auth_failure:
        failures.append(f"health endpoint: {health_auth_failure}")
    if health.status is not None and not _same_origin(public_url, health.final_url):
        failures.append(
            "health endpoint completed at a different origin " f"{_display_url(health.final_url)}"
        )
    if (
        health.status is not None
        and 200 <= health.status < 300
        and not _health_body_is_ok(health.body_preview)
    ):
        failures.append("health endpoint did not return an explicit healthy body")

    return DeploymentReport(
        checked_at_utc=datetime.now(UTC).isoformat(timespec="seconds"),
        public_url=public_url,
        page=page,
        health=health,
        failures=tuple(dict.fromkeys(failures)),
    )


def _single_line(value: object) -> str:
    return " ".join(str(value).splitlines()).strip()


def _display_url(url: str) -> str:
    """Keep redirect evidence while redacting credential-like query values."""

    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted_query = [
        (key, "REDACTED" if key.casefold() in SENSITIVE_QUERY_KEYS else value)
        for key, value in query
    ]
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(redacted_query), "")
    )


def _format_redirects(prefix: str, redirects: tuple[RedirectHop, ...]) -> list[str]:
    lines = [f"{prefix}_REDIRECT_COUNT={len(redirects)}"]
    for index, hop in enumerate(redirects, start=1):
        lines.append(
            f"{prefix}_REDIRECT_{index}={hop.status}|{_single_line(_display_url(hop.source_url))}|"
            f"{_single_line(_display_url(hop.target_url))}"
        )
    return lines


def format_report(report: DeploymentReport) -> str:
    """Return a deterministic line-oriented report suitable for CI logs."""

    lines = [
        f"CHECKED_AT_UTC={report.checked_at_utc}",
        "COOKIE_MODE=FRESH_EPHEMERAL_IN_MEMORY",
        f"REQUESTED_URL={_single_line(_display_url(report.public_url))}",
        f"PROBE_URL={_single_line(_display_url(report.page.requested_url))}",
        f"PAGE_STATUS={report.page.status if report.page.status is not None else 'UNAVAILABLE'}",
        f"FINAL_URL={_single_line(_display_url(report.page.final_url))}",
        *_format_redirects("PAGE", report.page.redirects),
        f"HEALTH_URL={_single_line(_display_url(report.health.requested_url))}",
        f"HEALTH_STATUS={report.health.status if report.health.status is not None else 'UNAVAILABLE'}",
        f"HEALTH_FINAL_URL={_single_line(_display_url(report.health.final_url))}",
        *_format_redirects("HEALTH", report.health.redirects),
        f"HEALTH_BODY={_single_line(report.health.body_preview)[:200]}",
        f"RESULT={'PASS' if report.passed else 'FAIL'}",
    ]
    lines.extend(f"FAILURE={_single_line(failure)}" for failure in report.failures)
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Check anonymous public reachability, redirect routes, and the Streamlit health endpoint."
        )
    )
    parser.add_argument("url", help="Deployed app URL, for example https://name.streamlit.app/")
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Per-request timeout in seconds (default: 15).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = check_deployment(args.url, timeout=args.timeout)
    except ValueError as exc:
        print(f"ERROR={_single_line(exc)}", file=sys.stderr)
        return 2
    print(format_report(report))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
