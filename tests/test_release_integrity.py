"""Repository-level checks for a safe, portable Streamlit release."""

from __future__ import annotations

import ast
import os
import re
import stat
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_SURFACES = (
    PROJECT_ROOT / "app.py",
    *sorted((PROJECT_ROOT / "app_pages").glob("*.py")),
    *sorted((PROJECT_ROOT / "src").glob("*.py")),
)


def _requirement_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _requirement_name(specification: str) -> str:
    match = re.match(r"[A-Za-z0-9_.-]+", specification)
    assert match is not None, f"Invalid dependency specification: {specification}"
    return match.group(0).lower().replace("_", "-")


def _exists_with_exact_case(relative_path: str) -> bool:
    current = PROJECT_ROOT
    for component in Path(relative_path).parts:
        if component not in {child.name for child in current.iterdir()}:
            return False
        current /= component
    return current.is_file()


def test_release_source_files_and_local_launchers_exist() -> None:
    required_files = (
        "app.py",
        "README.md",
        "DEPLOYMENT.md",
        "RELEASE_CHECKLIST.md",
        "requirements.txt",
        "requirements-dev.txt",
        "pyproject.toml",
        ".streamlit/config.toml",
        ".github/workflows/ci.yml",
        ".gitignore",
        ".dockerignore",
        "Dockerfile",
        "run_local.sh",
        "run_macos.command",
        "run_windows.bat",
        "assets/logo.svg",
        "assets/styles.css",
        "scripts/check_public_deployment.py",
    )
    missing = [path for path in required_files if not (PROJECT_ROOT / path).is_file()]
    assert not missing, f"Required release source files are missing: {missing}"

    if os.name != "nt":
        for launcher in ("run_local.sh", "run_macos.command"):
            mode = (PROJECT_ROOT / launcher).stat().st_mode
            assert mode & stat.S_IXUSR, f"{launcher} must be executable by its owner"


def test_runtime_dependencies_are_exactly_pinned_and_dev_tools_are_separate() -> None:
    runtime = _requirement_lines(PROJECT_ROOT / "requirements.txt")
    development = _requirement_lines(PROJECT_ROOT / "requirements-dev.txt")
    package = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    exact_pin = re.compile(r"^[A-Za-z0-9_.-]+==[^<>=!~\s]+$")
    assert runtime and all(exact_pin.fullmatch(line) for line in runtime)
    assert development[0] == "-r requirements.txt"
    assert all(exact_pin.fullmatch(line) for line in development[1:])

    runtime_names = {_requirement_name(line) for line in runtime}
    development_names = {_requirement_name(line) for line in development[1:]}
    assert runtime_names == {
        "streamlit",
        "numpy",
        "pandas",
        "plotly",
        "matplotlib",
        "reportlab",
    }
    assert development_names == {"pytest", "pytest-cov", "ruff", "black", "mypy"}
    assert runtime_names.isdisjoint(development_names)
    assert package["project"]["dependencies"] == runtime
    assert package["project"]["optional-dependencies"]["dev"] == development[1:]


def test_streamlit_configuration_is_private_headless_and_browser_safe() -> None:
    config = tomllib.loads((PROJECT_ROOT / ".streamlit/config.toml").read_text(encoding="utf-8"))

    assert config["server"]["headless"] is True
    assert config["server"]["enableCORS"] is True
    assert config["server"]["enableXsrfProtection"] is True
    assert config["browser"]["gatherUsageStats"] is False
    assert config["client"]["showErrorDetails"] == "none"
    assert config["theme"]["font"] == "sans-serif"
    assert config["theme"]["backgroundColor"].startswith("#")
    assert config["theme"]["secondaryBackgroundColor"].startswith("#")
    assert config["theme"]["primaryColor"] != config["theme"]["backgroundColor"]
    assert config["theme"]["textColor"] != config["theme"]["backgroundColor"]


def test_navigation_and_page_links_use_existing_case_exact_paths() -> None:
    application_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
    navigation_paths = re.findall(r'st\.Page\(\s*"([^"]+\.py)"', application_source)
    assert navigation_paths == [
        "app_pages/1_Simulator.py",
        "app_pages/2_Hand_Calculation.py",
        "app_pages/3_Results_and_Charts.py",
        "app_pages/4_Theory_and_Assumptions.py",
        "app_pages/5_Report_and_Export.py",
        "app_pages/6_About_Project.py",
    ]

    linked_paths: set[str] = set(navigation_paths)
    for page in sorted((PROJECT_ROOT / "app_pages").glob("*.py")):
        linked_paths.update(re.findall(r'st\.page_link\(\s*"([^"]+\.py)"', page.read_text()))

    mismatched = sorted(path for path in linked_paths if not _exists_with_exact_case(path))
    assert not mismatched, f"Missing or case-mismatched page paths: {mismatched}"


def test_public_python_surfaces_parse_without_unsafe_runtime_dependencies() -> None:
    forbidden_imports = {"aiohttp", "httpx", "requests", "socket", "subprocess", "urllib.request"}
    forbidden_calls = {"eval", "exec"}

    for path in PYTHON_SURFACES:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        imports: set[str] = set()
        calls: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                calls.add(node.func.id)

        assert not (imports & forbidden_imports), f"Unsafe runtime import in {path.name}"
        assert not (calls & forbidden_calls), f"Unsafe code execution in {path.name}"
        assert "st.secrets" not in source
        assert "os.environ" not in source
        assert "file_uploader" not in source


def test_public_files_have_no_personal_paths_secrets_or_prohibited_product_name() -> None:
    text_surfaces = [
        *PYTHON_SURFACES,
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "DEPLOYMENT.md",
        PROJECT_ROOT / "RELEASE_CHECKLIST.md",
        *sorted((PROJECT_ROOT / "docs").glob("*.md")),
        PROJECT_ROOT / "run_local.sh",
        PROJECT_ROOT / "run_macos.command",
        PROJECT_ROOT / "run_windows.bat",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in text_surfaces)

    assert not re.search(r"/(?:Users|home)/[^/\s]+", combined)
    assert not re.search(r"[A-Za-z]:\\Users\\", combined)
    assert "CFD Simulator" not in combined
    assert not (PROJECT_ROOT / ".streamlit/secrets.toml").exists()
    assert not list(PROJECT_ROOT.glob(".env*"))


def test_ignore_files_cover_release_exclusions_and_streamlit_secrets() -> None:
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
    for pattern in (
        ".venv/",
        "__pycache__/",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        ".coverage",
        "*.egg-info/",
        ".DS_Store",
        "__MACOSX/",
        ".streamlit/secrets.toml",
        "*.zip",
    ):
        assert pattern in gitignore
    for pattern in (
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".coverage",
        "*.egg-info",
        ".DS_Store",
        "__MACOSX",
        ".streamlit/secrets.toml",
        "*.zip",
    ):
        assert pattern in dockerignore


def test_deployment_documentation_records_verified_public_release() -> None:
    deployment = (PROJECT_ROOT / "DEPLOYMENT.md").read_text(encoding="utf-8")
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    checklist = (PROJECT_ROOT / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8")
    public_url = "https://jetforce-studio-mec350.streamlit.app/"

    assert public_url in deployment
    assert public_url in readme
    assert "PUBLIC_APP_URL_TO_BE_ADDED_AFTER_DEPLOYMENT" not in deployment
    assert (PROJECT_ROOT / "presentation_backup" / "public_app_qr.png").is_file()
    actual_deployment = checklist.split(
        "## Actual public deployment - complete only after deployment", maxsplit=1
    )[1]
    for completed_item in (
        "Repository pushed to the selected GitHub account.",
        "Streamlit Community Cloud app created from `app.py`.",
        "Deployment access set to Public.",
        "Final public URL recorded in `DEPLOYMENT.md`.",
        "Signed-out incognito/private-window test passed.",
        "Public study CSV and case CSV/JSON/HTML/PDF downloads passed.",
        "Final QR code generated from the real public URL.",
    ):
        assert f"- [x] {completed_item}" in actual_deployment
    for pending_item in (
        "Second-browser test passed.",
        "Phone test passed.",
        "Mobile-data test passed.",
    ):
        assert f"- [ ] {pending_item}" in actual_deployment
    assert "The application is actually deployed." in checklist
