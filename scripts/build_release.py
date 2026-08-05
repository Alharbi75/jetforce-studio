#!/usr/bin/env python3
"""Create and verify the clean public JetForce Studio release archive."""

from __future__ import annotations

import stat
import zipfile
from datetime import date
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = "JetForce_Studio"
RELEASE_DATE = date.today()
RELEASE_FILENAME = f"JetForce_Studio_Public_Release_{RELEASE_DATE.isoformat()}.zip"

ROOT_FILES = (
    ".dockerignore",
    ".gitignore",
    "AGENTS.md",
    "DEPLOYMENT.md",
    "Dockerfile",
    "README.md",
    "RELEASE_CHECKLIST.md",
    "app.py",
    "pyproject.toml",
    "requirements-dev.txt",
    "requirements.txt",
    "run_local.sh",
    "run_macos.command",
    "run_windows.bat",
)
SOURCE_DIRECTORIES = (
    ".github",
    ".streamlit",
    "app_pages",
    "assets",
    "docs",
    "presentation_backup",
    "scripts",
    "src",
    "tests",
)
FORBIDDEN_PARTS = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".vscode",
    "__MACOSX",
    "__pycache__",
    "build",
    "dist",
    "env",
    "htmlcov",
    "output",
    "tmp",
    "venv",
}
FORBIDDEN_NAMES = {
    ".coverage",
    ".DS_Store",
    ".env",
    "secrets.toml",
}
FORBIDDEN_SUFFIXES = {".log", ".pyc", ".pyo", ".swp", ".zip"}


def _is_forbidden(relative_path: Path) -> bool:
    return (
        bool(set(relative_path.parts) & FORBIDDEN_PARTS)
        or relative_path.name in FORBIDDEN_NAMES
        or relative_path.suffix.lower() in FORBIDDEN_SUFFIXES
        or relative_path.name.endswith(".egg-info")
    )


def release_files() -> tuple[Path, ...]:
    """Return the sorted, explicit release manifest and reject unsafe entries."""

    candidates = [ROOT / name for name in ROOT_FILES]
    for directory_name in SOURCE_DIRECTORIES:
        directory = ROOT / directory_name
        if not directory.is_dir() or directory.is_symlink():
            raise RuntimeError(f"Required release directory is missing or unsafe: {directory_name}")
        candidates.extend(path for path in directory.rglob("*") if path.is_file())

    files: list[Path] = []
    for path in candidates:
        if not path.exists():
            raise RuntimeError(f"Required release file is missing: {path.relative_to(ROOT)}")
        if path.is_symlink():
            raise RuntimeError(
                f"Release archives cannot contain symlinks: {path.relative_to(ROOT)}"
            )
        relative = path.relative_to(ROOT)
        if _is_forbidden(relative):
            continue
        if path.stat().st_size > 25 * 1024 * 1024:
            raise RuntimeError(f"Unexpectedly large release file: {relative}")
        files.append(path)
    return tuple(sorted(set(files), key=lambda item: item.relative_to(ROOT).as_posix()))


def build_release(destination: Path | None = None) -> Path:
    """Write a deterministic archive and verify every CRC and manifest entry."""

    target = destination or ROOT / RELEASE_FILENAME
    if target.parent != ROOT or target.name != RELEASE_FILENAME:
        raise RuntimeError("The release archive must use the documented repository-root filename.")

    files = release_files()
    with zipfile.ZipFile(
        target,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in files:
            relative = path.relative_to(ROOT)
            archive_name = (PurePosixPath(ARCHIVE_ROOT) / relative.as_posix()).as_posix()
            info = zipfile.ZipInfo(
                archive_name,
                date_time=(RELEASE_DATE.year, RELEASE_DATE.month, RELEASE_DATE.day, 12, 0, 0),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | (path.stat().st_mode & 0o777)) << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)

    expected_names = {
        (PurePosixPath(ARCHIVE_ROOT) / path.relative_to(ROOT).as_posix()).as_posix()
        for path in files
    }
    with zipfile.ZipFile(target) as archive:
        actual_names = set(archive.namelist())
        if actual_names != expected_names:
            raise RuntimeError("The generated release manifest does not match the source manifest.")
        failed_member = archive.testzip()
        if failed_member is not None:
            raise RuntimeError(f"Release CRC verification failed: {failed_member}")
        for info in archive.infolist():
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts:
                raise RuntimeError(f"Unsafe archive member: {info.filename}")
            relative = Path(*member.parts[1:])
            if _is_forbidden(relative):
                raise RuntimeError(f"Forbidden archive member: {info.filename}")
    return target


def main() -> None:
    archive = build_release()
    with zipfile.ZipFile(archive) as stream:
        members = [item for item in stream.infolist() if not item.is_dir()]
        largest = sorted(members, key=lambda item: item.file_size, reverse=True)[:5]
    print(f"ARCHIVE={archive.name}")
    print(f"SIZE_BYTES={archive.stat().st_size}")
    print(f"FILE_COUNT={len(members)}")
    for item in largest:
        print(f"LARGEST={item.filename}|{item.file_size}")


if __name__ == "__main__":
    main()
