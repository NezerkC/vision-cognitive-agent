import json

import pytest
from fastapi.testclient import TestClient

import sentidos.calibrador_audio as calibrador
import sentidos.habla_parietal as habla_module
import sentidos.oido_parietal as oido_module
import sentidos.vision_parietal as vision_module
from sentidos.vision_parietal import ScreenCaptureError, VisionParietal


class FakeWriter:
    def __init__(self):
        self.events = []

    def write(self, data: bytes):
        self.events.append(json.loads(data.decode("utf-8")))

    async def drain(self):
        pass


class FakeShot:
    size = (2, 2)
    bgra = bytes([10, 20, 30, 0] * 4)


class FakeMss:
    monitors = [{}, {"left": 0, "top": 0, "width": 2, "height": 2}]

    def grab(self, monitor):
        return FakeShot()


def _failing_mss():
    raise OSError("no display")


# --- Vision -----------------------------------------------------------------


def test_vision_does_not_fall_back_to_mock_when_capture_cannot_start(monkeypatch):
    monkeypatch.setattr(vision_module.mss, "mss", _failing_mss)

    vision = VisionParietal()

    assert vision.force_mock is False
    with pytest.raises(ScreenCaptureError, match="no display"):
        vision.capture_screenshot()


def test_vision_raises_instead_of_returning_a_fake_frame(monkeypatch):
    class BrokenMss(FakeMss):
        def grab(self, monitor):
            raise OSError("grab failed")

    monkeypatch.setattr(vision_module.mss, "mss", BrokenMss)

    with pytest.raises(ScreenCaptureError, match="grab failed"):
        VisionParietal().capture_screenshot()


def test_vision_starts_capturing_after_switching_from_mock_to_real(monkeypatch):
    monkeypatch.setattr(vision_module.mss, "mss", FakeMss)
    vision = VisionParietal(force_mock=True)

    vision.force_mock = False
    image = vision.capture_screenshot()

    assert image.size == (2, 2)


@pytest.mark.asyncio
async def test_vision_announces_each_distinct_capture_error_once():
    vision, writer = VisionParietal(force_mock=True), FakeWriter()

    await vision.report_capture_error(writer, "no display")
    await vision.report_capture_error(writer, "no display")
    await vision.report_capture_error(writer, "monitor 2 missing")

    messages = [e["data"]["mensaje"] for e in writer.events if e["topic"] == "canal.sistema.anuncios"]
    assert len(messages) == 2
    assert "no display" in messages[0]


# --- Hearing ----------------------------------------------------------------


def test_hearing_reports_missing_packages_instead_of_idling_as_mock(monkeypatch):
    monkeypatch.setattr(oido_module, "pyaudio", None)
    monkeypatch.setattr(oido_module, "faster_whisper", None)

    oido = oido_module.OidoParietal()

    assert oido.force_mock is False
    assert "PyAudio" in oido.unavailable_reason
    assert "faster-whisper" in oido.unavailable_reason


@pytest.mark.asyncio
async def test_hearing_announces_why_it_is_unavailable(monkeypatch):
    monkeypatch.setattr(oido_module, "pyaudio", None)
    oido, writer = oido_module.OidoParietal(), FakeWriter()

    await oido.announce_unavailable(writer)

    announcement = writer.events[0]
    assert announcement["topic"] == "canal.sistema.anuncios"
    assert "PyAudio" in announcement["data"]["mensaje"]


def test_hearing_explicit_mock_needs_no_packages(monkeypatch):
    monkeypatch.setattr(oido_module, "pyaudio", None)

    oido = oido_module.OidoParietal(force_mock=True)

    assert oido.unavailable_reason is None


# --- Speech -----------------------------------------------------------------


def test_speech_reports_when_no_tts_engine_is_installed(monkeypatch):
    monkeypatch.setattr(habla_module, "module_available", lambda name: False)

    habla = habla_module.HablaParietal()

    assert "edge-tts" in habla.unavailable_reason
    assert "pyttsx3" in habla.unavailable_reason


@pytest.mark.asyncio
async def test_speech_does_not_pretend_to_speak_when_unavailable(monkeypatch):
    monkeypatch.setattr(habla_module, "module_available", lambda name: False)

    assert await habla_module.HablaParietal().speak("hola") is False


# --- Audio learning and calibration -----------------------------------------


def test_failed_audio_transcription_is_an_error_and_saves_nothing(monkeypatch):
    import sentidos.sistema_periferico as gateway

    published = []

    async def record(topic, data):
        published.append(topic)
        return True

    monkeypatch.setattr(gateway.gateway, "publish_event", record)

    resp = TestClient(gateway.app).post("/api/memoria/aprender", files={"file": ("nota.wav", b"not really audio")})

    assert resp.status_code >= 400
    assert published == []


def test_calibration_without_pyaudio_fails_instead_of_simulating(monkeypatch, capsys):
    monkeypatch.setattr(calibrador, "pyaudio", None)

    assert calibrador.run_calibration() == 1
    out = capsys.readouterr().out
    assert "PyAudio" in out
    assert "MOCK" not in out
    assert not hasattr(calibrador, "run_mock_calibration")
