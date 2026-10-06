import pytest

import mesh_worker


@pytest.mark.unit
def test_package_version() -> None:
    """T-BOOT-WRK: the worker runtime package imports and exposes its version."""
    assert mesh_worker.__version__ == "0.1.0"
