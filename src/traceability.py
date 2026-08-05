"""Safe application and model traceability metadata.

The helpers in this module expose only allowlisted build identifiers.  They do
not invoke Git, traverse caller-provided paths, or reveal environment contents.
"""

from __future__ import annotations

import os
import re
import tomllib
from collections.abc import Mapping
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

MODEL_REVISION = "MEC350-CV-2D-R1"
LOCAL_BUILD = "local build"
_PROJECT_NAME = "jetforce-studio"
_PROJECT_FILE = Path(__file__).resolve().parents[1] / "pyproject.toml"
_BUILD_KEYS = (
    "JETFORCE_BUILD_COMMIT",
    "GITHUB_SHA",
    "SOURCE_VERSION",
    "VERCEL_GIT_COMMIT_SHA",
    "RENDER_GIT_COMMIT",
)
_COMMIT_PATTERN = re.compile(r"[0-9a-fA-F]{7,64}")


def application_version() -> str:
    """Return the source-tree version, with a safe installed-package fallback."""

    project_version: str | None = None
    try:
        with _PROJECT_FILE.open("rb") as stream:
            project = tomllib.load(stream)["project"]
        value = project["version"]
        if isinstance(value, str) and value.strip():
            project_version = value.strip()
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError):
        project_version = None

    if project_version is not None:
        return project_version

    try:
        installed = version(_PROJECT_NAME)
    except PackageNotFoundError:
        return "unversioned"
    return installed.strip() or "unversioned"


def build_commit(environment: Mapping[str, str] | None = None) -> str:
    """Return an allowlisted hexadecimal build commit or ``local build``."""

    for key in _BUILD_KEYS:
        raw_value = environment.get(key) if environment is not None else os.getenv(key)
        if raw_value is None:
            continue
        candidate = raw_value.strip()
        if _COMMIT_PATTERN.fullmatch(candidate):
            return candidate.lower()
    return LOCAL_BUILD


def generation_timestamp(value: datetime | None = None) -> str:
    """Return a second-resolution ISO 8601 timestamp normalized to UTC."""

    moment = datetime.now(UTC) if value is None else value
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).isoformat(timespec="seconds")


def traceability_metadata(generated_at: datetime | None = None) -> dict[str, str]:
    """Return the complete public software/model traceability mapping."""

    return {
        "application_version": application_version(),
        "model_revision": MODEL_REVISION,
        "build_commit": build_commit(),
        "generated_at": generation_timestamp(generated_at),
    }


__all__ = [
    "LOCAL_BUILD",
    "MODEL_REVISION",
    "application_version",
    "build_commit",
    "generation_timestamp",
    "traceability_metadata",
]
