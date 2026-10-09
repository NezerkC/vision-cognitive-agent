import asyncio

import pytest

import core.orchestrator as orchestrator_module
from core.main import load_project_env
from core.orchestrator import BrainstemOrchestrator


@pytest.mark.asyncio
async def test_supervisor_restarts_a_crashed_service_with_a_fresh_coroutine(monkeypatch):
    """A coroutine object can be awaited once; restarting must build a new one from a factory."""
    monkeypatch.setattr(orchestrator_module, "RESTART_DELAY_SECONDS", 0)
    orchestrator = BrainstemOrchestrator(use_mock=True, enable_tcp_bridge=False)
    runs = []

    async def flaky_service():
        runs.append(len(runs) + 1)
        if len(runs) == 1:
            raise RuntimeError("boom")
        orchestrator.should_run = False

    await asyncio.wait_for(orchestrator._supervise("flaky", flaky_service), 2)

    assert runs == [1, 2]


def test_orchestrator_runs_the_web_gateway():
    """Without sistema_periferico there is no port 8000: no GUI, no Vision Studio API or WebSocket."""
    orchestrator = BrainstemOrchestrator(use_mock=True, enable_tcp_bridge=False)

    names = [name for name, _ in orchestrator.service_factories(lancedb_mgr=None, lancedb_mock=True)]

    assert "Sistema Periférico" in names


def test_no_service_consumes_a_topic_nothing_publishes():
    """Hipocampo waited for canal.sistema.fin_tarea and the web search daemon for canal.web.busqueda; no
    service publishes either, so both are gone (the pineal daemon summarizes activity, the graph searches)."""
    orchestrator = BrainstemOrchestrator(use_mock=True, enable_tcp_bridge=False)

    names = [name for name, _ in orchestrator.service_factories(lancedb_mgr=None, lancedb_mock=True)]

    assert "Hipocampo" not in names
    assert "Web Search" not in names


def test_service_factories_do_not_start_anything():
    orchestrator = BrainstemOrchestrator(use_mock=True, enable_tcp_bridge=False)

    factories = orchestrator.service_factories(lancedb_mgr=None, lancedb_mock=True)

    assert all(callable(factory) for _, factory in factories)


def test_load_project_env_fills_missing_variables_without_overriding_the_shell(tmp_path):
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=from-file\nTAVILY_API_KEY=tavily-file\n", encoding="utf-8")
    environ = {"OPENROUTER_API_KEY": "from-shell"}

    load_project_env(str(tmp_path), environ)

    assert environ == {"OPENROUTER_API_KEY": "from-shell", "TAVILY_API_KEY": "tavily-file"}
