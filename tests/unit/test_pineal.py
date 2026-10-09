import inspect

import pytest

from daemons.pineal_daemon import ACTIVITY_TOPICS, PinealDaemon


class SavedMemories:
    def __init__(self):
        self.calls = []

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return {"status": "success"}


@pytest.fixture
def isolated_memory(tmp_path, monkeypatch):
    """The memory stores use relative paths; run from a temp dir so tests never touch the real memoria_activa."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _daemon(monkeypatch, summarizer):
    daemon = PinealDaemon(summarizer=summarizer)
    saved = SavedMemories()
    monkeypatch.setattr(daemon.cerebelo, "guardar_recuerdo", saved)
    return daemon, saved


def test_webhooks_and_uploads_are_activity_for_the_daily_summary(monkeypatch):
    daemon, _ = _daemon(monkeypatch, None)

    daemon.record_activity("canal.sensorial.periferico", {"event": "git_push", "repo": "vision-os"})
    daemon.record_activity("canal.sensorial.archivo_recibido", {"nombre": "notas.txt", "ruta_local": "/tmp/notas.txt"})

    assert daemon.activity_log == [
        'Webhook externo: {"event": "git_push", "repo": "vision-os"}',
        "Archivo recibido: notas.txt",
    ]


def test_pineal_subscribes_to_every_activity_topic_it_records():
    assert {"canal.sensorial.periferico", "canal.sensorial.archivo_recibido"} <= set(ACTIVITY_TOPICS)


def test_sleep_waits_for_a_real_idle_period():
    assert inspect.signature(PinealDaemon).parameters["idle_threshold_seconds"].default >= 600


@pytest.mark.asyncio
async def test_no_activity_means_no_summary(monkeypatch):
    async def must_not_run(prompt):
        raise AssertionError("nothing happened, so there is nothing to summarize")

    daemon, saved = _daemon(monkeypatch, must_not_run)

    assert await daemon.generate_context_summary() is None
    assert saved.calls == []


@pytest.mark.asyncio
async def test_summary_comes_from_the_recorded_activity(monkeypatch):
    prompts = []

    async def summarize(prompt):
        prompts.append(prompt)
        return "El usuario depuró un error de FFmpeg y pidió una búsqueda web."

    daemon, saved = _daemon(monkeypatch, summarize)
    daemon.record_activity("canal.sistema.contexto_actual", {"contexto": "ANOMALIA_DETECTADA: FFmpeg crashed"})
    daemon.record_activity("canal.cognitivo.entrada", {"prompt": "busca cómo arreglar ffmpeg"})
    daemon.record_activity("canal.sensorial.vision", {"image": "QUJD"})

    summary = await daemon.generate_context_summary()

    assert summary == "El usuario depuró un error de FFmpeg y pidió una búsqueda web."
    assert "FFmpeg crashed" in prompts[0] and "busca cómo arreglar ffmpeg" in prompts[0]
    assert "QUJD" not in prompts[0]
    assert saved.calls[0]["texto"] == summary
    assert saved.calls[0]["metadata"]["tipo"] == "resumen_diario"
    assert await daemon.generate_context_summary() is None


@pytest.mark.asyncio
async def test_failed_summary_saves_nothing_and_keeps_the_activity(monkeypatch):
    async def unavailable(prompt):
        raise ConnectionError("LLM caído")

    daemon, saved = _daemon(monkeypatch, unavailable)
    daemon.record_activity("canal.cognitivo.entrada", {"prompt": "hola"})

    assert await daemon.generate_context_summary() is None
    assert saved.calls == []
    assert daemon.activity_log == ["Petición: hola"]


@pytest.mark.asyncio
async def test_consolidation_moves_low_w_rows_without_duplicating(isolated_memory):
    daemon = PinealDaemon()
    daemon.cerebelo.init_memory(mock_embedder=True)
    # Hot rows whose W decayed below the threshold after they were stored.
    embed = daemon.db_manager.embedder.embed_query
    daemon.db_manager.table.add(
        [
            {
                "vector": embed(texto),
                "text": texto,
                "coordenada_x": 0.0,
                "coordenada_y": 0.0,
                "coordenada_z": 0.0,
                "coordenada_w": w,
                "escala_magnitud": "KB",
                "metadata": "{}",
            }
            for texto, w in (("recuerdo frío", 20.0), ("recuerdo caliente", 90.0))
        ]
    )

    first = await daemon.run_consolidation()
    second = await daemon.run_consolidation()

    hot = [r["text"] for r in daemon.db_manager.table.to_arrow().to_pylist()]
    cold = [r["text"] for r in daemon.db_manager.cold_table.to_arrow().to_pylist()]
    assert first["consolidated_items"] == 1
    assert second["consolidated_items"] == 0
    assert hot == ["recuerdo caliente"]
    assert cold == ["recuerdo frío"]
