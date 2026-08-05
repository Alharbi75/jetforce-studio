"""Tests for safe version, model-revision, build, and timestamp metadata."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.traceability import (
    LOCAL_BUILD,
    MODEL_REVISION,
    application_version,
    build_commit,
    generation_timestamp,
    traceability_metadata,
)


def test_application_version_matches_project_metadata() -> None:
    assert application_version() == "2.0.0"


def test_build_commit_has_safe_fallback_and_accepts_only_hexadecimal_ids() -> None:
    assert build_commit({}) == LOCAL_BUILD
    assert build_commit({"GITHUB_SHA": "ABCDEF1234567890"}) == "abcdef1234567890"
    assert build_commit({"GITHUB_SHA": "refs/heads/main"}) == LOCAL_BUILD
    assert build_commit({"GITHUB_SHA": "abc123"}) == LOCAL_BUILD
    assert build_commit({"GITHUB_SHA": "a" * 65}) == LOCAL_BUILD


def test_build_commit_uses_allowlist_priority() -> None:
    assert (
        build_commit(
            {
                "JETFORCE_BUILD_COMMIT": "1234567",
                "GITHUB_SHA": "abcdef1234567890",
                "UNRELATED_SECRET": "do-not-expose",
            }
        )
        == "1234567"
    )


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (datetime(2026, 8, 5, 1, 2, 3), "2026-08-05T01:02:03+00:00"),
        (
            datetime(2026, 8, 5, 5, 2, 3, tzinfo=timezone(timedelta(hours=4))),
            "2026-08-05T01:02:03+00:00",
        ),
    ],
)
def test_generation_timestamp_is_second_resolution_utc(moment: datetime, expected: str) -> None:
    assert generation_timestamp(moment) == expected


def test_traceability_metadata_is_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "JETFORCE_BUILD_COMMIT",
        "GITHUB_SHA",
        "SOURCE_VERSION",
        "VERCEL_GIT_COMMIT_SHA",
        "RENDER_GIT_COMMIT",
    ):
        monkeypatch.delenv(key, raising=False)
    fixed = datetime(2026, 8, 5, 9, 30, tzinfo=UTC)

    assert traceability_metadata(fixed) == {
        "application_version": "2.0.0",
        "model_revision": MODEL_REVISION,
        "build_commit": LOCAL_BUILD,
        "generated_at": "2026-08-05T09:30:00+00:00",
    }
