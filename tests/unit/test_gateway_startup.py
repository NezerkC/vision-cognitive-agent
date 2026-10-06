import asyncio
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_gateway_import_does_not_create_the_notebooks_manager():
    """Creating it loads the BGE-M3 model, which used to delay the gateway's startup by tens of seconds."""
    code = "import sys, sentidos.sistema_periferico as g; sys.exit(0 if g._cuadernos_mgr is None else 3)"
    env = {**os.environ, "PYTHONPATH": ROOT}

    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, timeout=300)

    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")[-2000:]


@pytest.mark.asyncio
async def test_notebooks_manager_is_created_once_under_concurrent_requests(monkeypatch):
    import sentidos.sistema_periferico as gateway

    created = []

    class FakeManager:
        def __init__(self):
            created.append(self)

    monkeypatch.setattr(gateway, "CuadernosManager", FakeManager)
    monkeypatch.setattr(gateway, "_cuadernos_mgr", None)

    managers = await asyncio.gather(*(gateway.get_cuadernos_mgr() for _ in range(5)))

    assert len(created) == 1
    assert all(m is created[0] for m in managers)
