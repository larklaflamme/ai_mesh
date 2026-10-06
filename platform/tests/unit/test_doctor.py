"""`mesh doctor` reports each check independently and fails closed (WP-B §9)."""

import socket

import pytest
from typer.testing import CliRunner

from mesh.cli.doctor import CheckResult, check_conda_env, check_tcp, overall_ok, run_checks


@pytest.mark.unit
def test_conda_env_check() -> None:
    """T-BOOT-06: the conda check passes only for ai-mesh."""
    assert check_conda_env({"CONDA_DEFAULT_ENV": "ai-mesh"}).ok
    assert not check_conda_env({"CONDA_DEFAULT_ENV": "base"}).ok
    assert not check_conda_env({}).ok


@pytest.mark.unit
def test_overall_fails_closed() -> None:
    """T-BOOT-06: any failed required check fails the run; an empty result list is not OK."""
    ok = CheckResult("a", True, "")
    bad = CheckResult("b", False, "")
    optional_bad = CheckResult("c", False, "", required=False)
    assert overall_ok([ok, optional_bad])
    assert not overall_ok([ok, bad])
    assert not overall_ok([])


@pytest.mark.unit
def test_checks_run_independently() -> None:
    """T-BOOT-06: a failing check does not stop later checks from running."""
    results = run_checks(
        [lambda: CheckResult("x", False, "down"), lambda: CheckResult("y", True, "")]
    )
    assert [r.name for r in results] == ["x", "y"]


@pytest.mark.unit
def test_tcp_check_unreachable() -> None:
    """T-BOOT-06: an unreachable port is reported as a failure with a reason."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]  # bound but not listening -> connection refused
        result = check_tcp("pg", f"postgresql://u@127.0.0.1:{port}/db")
    assert not result.ok
    assert "unreachable" in result.detail
    assert not check_tcp("pg", "not a url").ok


@pytest.mark.unit
def test_doctor_cli_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """T-BOOT-06: `mesh doctor` exits non-zero when a check fails, zero when all pass."""
    from mesh.cli.main import app

    monkeypatch.setattr(
        "mesh.cli.main.default_checks", lambda _s: [lambda: CheckResult("x", False, "down")]
    )
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "FAIL" in result.stdout

    monkeypatch.setattr(
        "mesh.cli.main.default_checks", lambda _s: [lambda: CheckResult("x", True, "up")]
    )
    assert CliRunner().invoke(app, ["doctor"]).exit_code == 0
