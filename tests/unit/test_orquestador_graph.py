import pytest

from cognitivo import orquestador_graph as og


def _state(**overrides):
    state = {
        "input_usuario": "qué recuerdo de ayer",
        "ruta_planeada": ["memoria"],
        "vagones_informacion": [],
        "respuesta_final": "",
        "request_id": "req-1",
        "mock": False,
    }
    state.update(overrides)
    return state


@pytest.mark.asyncio
async def test_memory_node_queries_injected_memory_search():
    calls = []

    async def fake_memory_search(request_id, query, emotion_filter="neutral"):
        calls.append((request_id, query))
        return [{"text": "Recuerdo relevante", "metadata": {"filename": "diario.md"}, "score": 0.9}]

    result = await og.nodo_memoria(_state(), {"configurable": {"memory_search": fake_memory_search}})

    assert calls == [("req-1", "qué recuerdo de ayer")]
    vagon = result["vagones_informacion"][0]
    assert vagon["resultado"] == [{"fichero": "diario.md", "texto": "Recuerdo relevante", "score": 0.9}]


@pytest.mark.asyncio
async def test_memory_node_reports_missing_search_engine():
    result = await og.nodo_memoria(_state(), {"configurable": {}})

    assert result["vagones_informacion"][0]["resultado"] == "No database search engine active."


@pytest.mark.asyncio
async def test_ejecutar_passes_memory_search_to_graph(monkeypatch):
    captured = {}

    class FakeGraph:
        async def ainvoke(self, state, config=None):
            captured["config"] = config
            return {"respuesta_final": "ok"}

    async def memory_search(*args, **kwargs):
        return []

    monkeypatch.setattr(og, "orquestador_graph", FakeGraph())

    assert await og.ejecutar_orquestador_graph("hola", "req-2", memory_search=memory_search) == "ok"
    assert captured["config"]["configurable"]["memory_search"] is memory_search
