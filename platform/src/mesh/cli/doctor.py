"""Environment checks behind ``mesh doctor``.

Each check is independent and reports its own result. Any failed required check makes the
whole doctor run fail (fail closed). Infrastructure checks are expected to fail before
Phase 0 brings the stack up; they still report a clear reason.
"""

import os
import socket
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from mesh.core.settings import MeshSettings

CONDA_ENV_NAME = "ai-mesh"
TIMEOUT_S = 3.0


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one doctor check."""

    name: str
    ok: bool
    detail: str
    required: bool = True


def check_conda_env(env: dict[str, str] | None = None) -> CheckResult:
    """The active conda environment must be ``ai-mesh``."""
    active = (env if env is not None else dict(os.environ)).get("CONDA_DEFAULT_ENV", "")
    if active == CONDA_ENV_NAME:
        return CheckResult("conda env", True, f"active: {active}")
    return CheckResult(
        "conda env", False, f"active: {active or '<none>'}; run `conda activate {CONDA_ENV_NAME}`"
    )


def check_docker() -> CheckResult:
    """The Docker daemon must answer a ping."""
    import docker  # local import: the SDK reads env/config on client creation
    from docker.errors import DockerException

    try:
        client = docker.from_env(timeout=int(TIMEOUT_S))
        try:
            client.ping()
            version = str(client.version().get("Version", "?"))
        finally:
            client.close()
    except DockerException as exc:
        return CheckResult("docker", False, f"unreachable: {type(exc).__name__}: {exc}")
    return CheckResult("docker", True, f"engine {version}")


def check_tcp(name: str, url: str) -> CheckResult:
    """A TCP connection to the host/port of ``url`` must succeed."""
    parts = urlsplit(url)
    host, port = parts.hostname, parts.port
    if host is None or port is None:
        return CheckResult(name, False, "no host/port in configured URL")
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT_S):
            pass
    except OSError as exc:
        return CheckResult(name, False, f"{host}:{port} unreachable: {exc}")
    return CheckResult(name, True, f"{host}:{port} reachable")


def check_http(name: str, url: str) -> CheckResult:
    """An HTTP GET on ``url`` must return 2xx."""
    try:
        response = httpx.get(url, timeout=TIMEOUT_S)
    except httpx.HTTPError as exc:
        return CheckResult(name, False, f"{url} unreachable: {type(exc).__name__}")
    if response.is_success:
        return CheckResult(name, True, f"{url} -> {response.status_code}")
    return CheckResult(name, False, f"{url} -> {response.status_code}")


def default_checks(settings: MeshSettings) -> list[Callable[[], CheckResult]]:
    """The checks ``mesh doctor`` runs, in order."""
    db_url = settings.database_url.get_secret_value()
    return [
        check_conda_env,
        check_docker,
        lambda: check_tcp("postgresql", db_url),
        lambda: check_http("qdrant", settings.qdrant_url.rstrip("/") + "/readyz"),
        lambda: check_http("gateway", settings.gateway_url.rstrip("/") + "/healthz"),
    ]


def run_checks(checks: list[Callable[[], CheckResult]]) -> list[CheckResult]:
    """Run every check; one check's failure never prevents the others from running."""
    return [check() for check in checks]


def overall_ok(results: list[CheckResult]) -> bool:
    """True only if every required check passed. An empty result list is not OK."""
    return bool(results) and all(r.ok for r in results if r.required)
