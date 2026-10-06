"""Bootstrap tests (WP-B), see design/09-implementation-guide/01-bootstrap.md §9."""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")  # Crockford base32
PLATFORM_DIR = Path(__file__).resolve().parents[2]


@pytest.mark.unit
@pytest.mark.parametrize("prefix", ["run", "task", "att", "gate", "evt", "exp"])
def test_new_id_format(prefix: str) -> None:
    """T-BOOT-01: new_id has the right prefix and a ULID body."""
    from mesh.core.ids import new_id

    value = new_id(prefix)
    head, _, body = value.partition("_")
    assert head == prefix
    assert ULID_RE.match(body)


@pytest.mark.unit
def test_new_id_sortable_by_creation_time() -> None:
    """T-BOOT-01: ids sort in creation order (ULID timestamp + monotonic randomness)."""
    from mesh.core.ids import new_id

    ids = [new_id("evt") for _ in range(200)]
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)


@pytest.mark.unit
def test_new_id_rejects_unknown_prefix() -> None:
    """T-BOOT-01: an unknown prefix is an error, not a silently accepted id."""
    from mesh.core.ids import new_id

    with pytest.raises(ValueError, match="unknown id prefix"):
        new_id("bogus")


@pytest.mark.unit
def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """T-BOOT-02: settings read MESH_* variables."""
    from mesh.core.settings import load_settings

    monkeypatch.chdir(tmp_path)  # no stray .env
    monkeypatch.setenv("MESH_QDRANT_URL", "http://qdrant.test:6333")
    monkeypatch.setenv("MESH_RUNS_ROOT", str(tmp_path / "runs"))
    monkeypatch.setenv("MESH_HIDDEN_ROOT", "/nonexistent/hidden")
    settings = load_settings()
    assert settings.qdrant_url == "http://qdrant.test:6333"
    assert settings.runs_root == tmp_path / "runs"
    assert settings.hidden_root == Path("/nonexistent/hidden")


@pytest.mark.unit
def test_settings_secrets_not_rendered(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """T-BOOT-02: secret-bearing settings do not appear in repr."""
    from mesh.core.settings import load_settings

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MESH_DATABASE_URL", "postgresql+psycopg://u:planted-pw@db:5432/x")
    settings = load_settings()
    assert "planted-pw" not in repr(settings)
    assert "planted-pw" in settings.database_url.get_secret_value()


@pytest.mark.unit
def test_import_does_not_load_settings(tmp_path: Path) -> None:
    """T-BOOT-02: importing every mesh module with no MESH_* env does not construct settings,
    i.e. nothing reads configuration at import time."""
    code = (
        "import importlib, pkgutil, mesh, mesh.core.settings as s\n"
        "def boom(*a, **k): raise RuntimeError('settings constructed at import time')\n"
        "s.MeshSettings.__init__ = boom\n"
        "for m in pkgutil.walk_packages(mesh.__path__, 'mesh.'): importlib.import_module(m.name)\n"
        "print('ok')\n"
    )
    env = {"PATH": "/usr/bin:/bin"}
    proc = subprocess.run(  # noqa: S603  # fixed argv, no shell
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ok"


@pytest.mark.unit
def test_error_hierarchy() -> None:
    """T-BOOT-03: InfraFailure and TaskFailure are distinct MeshErrors."""
    from mesh.core import errors

    assert issubclass(errors.InfraFailure, errors.MeshError)
    assert issubclass(errors.TaskFailure, errors.MeshError)
    assert not issubclass(errors.InfraFailure, errors.TaskFailure)
    assert not issubclass(errors.TaskFailure, errors.InfraFailure)
    for cls in (errors.PolicyViolation, errors.BudgetExceeded, errors.GateMismatch):
        assert issubclass(cls, errors.MeshError)


@pytest.mark.unit
def test_cli_version() -> None:
    """T-BOOT-04: `mesh version` exits 0 and prints the version."""
    from mesh import __version__
    from mesh.cli.main import app

    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


@pytest.mark.unit
def test_lint_imports_passes() -> None:
    """T-BOOT-05: import-linter contracts hold on the skeleton."""
    exe = shutil.which("lint-imports", path=str(Path(sys.executable).parent))
    assert exe is not None, "lint-imports not installed in this environment"
    proc = subprocess.run(  # noqa: S603  # fixed argv, no shell
        [exe],
        cwd=PLATFORM_DIR,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
