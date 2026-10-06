import pytest

import mesh_gateway


@pytest.mark.unit
def test_package_version() -> None:
    """T-BOOT-GW: the gateway package imports and exposes its version."""
    assert mesh_gateway.__version__ == "0.1.0"
