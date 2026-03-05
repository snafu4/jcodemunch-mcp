"""jcodemunch-mcp package metadata."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _version_from_pyproject() -> str | None:
    """Read project version from local pyproject.toml when running from source."""
    try:
        import tomllib

        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        return data.get("project", {}).get("version")
    except Exception:
        return None


def get_version() -> str:
    """Return the package version for installed and local-dev execution."""
    try:
        return version("jcodemunch-mcp")
    except PackageNotFoundError:
        return _version_from_pyproject() or "0+unknown"


__version__ = get_version()
