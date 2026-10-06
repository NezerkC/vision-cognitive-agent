import json

import pytest

from cognitivo.ejecutor_izquierdo import PENDING_TTL_SECONDS, EjecutorIzquierdo


class FakeWriter:
    def __init__(self):
        self.published = []

    def write(self, raw: bytes):
        self.published.append(json.loads(raw.decode("utf-8")))

    async def drain(self):
        pass

    def results(self):
        return [p["data"] for p in self.published if p.get("topic") == "canal.ejecucion.resultado"]


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def ejecutor(monkeypatch, clock):
    ejecutor = EjecutorIzquierdo(is_mock=False, clock=clock)
    ejecutor.executed = []

    async def fake_script(cmd):
        ejecutor.executed.append(("ejecutar_script", cmd))
        return {"status": "success", "exit_code": 0}

    async def fake_ui(commands):
        ejecutor.executed.append(("control_ui", commands))
        return {"status": "success"}

    monkeypatch.setattr(ejecutor, "execute_script", fake_script)
    monkeypatch.setattr(ejecutor, "execute_control_ui", fake_ui)
    return ejecutor


def _action(request_id="req-1", tool="ejecutar_script", params=("dir",)):
    return {"request_id": request_id, "herramienta": tool, "parametros": list(params)}


@pytest.mark.asyncio
async def test_action_is_not_executed_without_human_approval(ejecutor):
    writer = FakeWriter()

    await ejecutor.handle_action(_action(), writer)

    assert ejecutor.executed == []
    assert writer.results() == []


@pytest.mark.asyncio
async def test_approved_action_runs_once_and_publishes_its_result(ejecutor):
    writer = FakeWriter()
    await ejecutor.handle_action(_action(), writer)

    await ejecutor.handle_approval({"request_id": "req-1", "approved": True}, writer)
    await ejecutor.handle_approval({"request_id": "req-1", "approved": True}, writer)  # replay

    assert ejecutor.executed == [("ejecutar_script", "dir")]
    assert [r["resultado"]["status"] for r in writer.results()] == ["success"]


@pytest.mark.asyncio
async def test_rejected_action_never_runs(ejecutor):
    writer = FakeWriter()
    await ejecutor.handle_action(_action(tool="control_ui", params=("win",)), writer)

    await ejecutor.handle_approval({"request_id": "req-1", "approved": False}, writer)

    assert ejecutor.executed == []
    assert writer.results()[0]["resultado"]["status"] == "rejected"


@pytest.mark.asyncio
async def test_only_an_explicit_true_approves(ejecutor):
    writer = FakeWriter()
    await ejecutor.handle_action(_action(), writer)

    await ejecutor.handle_approval({"request_id": "req-1", "approved": "true"}, writer)

    assert ejecutor.executed == []


@pytest.mark.asyncio
async def test_expired_action_cannot_be_approved(ejecutor, clock):
    writer = FakeWriter()
    await ejecutor.handle_action(_action(), writer)

    clock.now += PENDING_TTL_SECONDS + 1
    await ejecutor.handle_approval({"request_id": "req-1", "approved": True}, writer)

    assert ejecutor.executed == []


@pytest.mark.asyncio
async def test_pending_request_cannot_be_swapped_before_approval(ejecutor):
    """The human approves what the ticket showed: a later action reusing the id must not replace it."""
    writer = FakeWriter()
    await ejecutor.handle_action(_action(params=("dir",)), writer)
    await ejecutor.handle_action(_action(params=("del /s /q C:\\",)), writer)

    await ejecutor.handle_approval({"request_id": "req-1", "approved": True}, writer)

    assert ejecutor.executed == [("ejecutar_script", "dir")]


@pytest.mark.asyncio
async def test_unsupported_tool_is_rejected_without_waiting_for_approval(ejecutor):
    writer = FakeWriter()

    await ejecutor.handle_action(_action(tool="formatear_disco"), writer)

    assert ejecutor.executed == []
    assert writer.results()[0]["resultado"]["status"] == "error"


@pytest.mark.asyncio
async def test_mock_mode_never_runs_a_real_shell(monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("a real shell was spawned in mock mode")

    monkeypatch.setattr("asyncio.create_subprocess_shell", forbidden)

    result = await EjecutorIzquierdo(is_mock=True).execute_script("echo hola")

    assert result["status"] == "success"
    assert "simulated" in result["detail"].lower()
