import io

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

import sentidos.sistema_periferico as gateway
from sentidos.limites_subida import DEFAULT_MAX_UPLOAD_BYTES, max_upload_bytes, read_upload_limited


def _upload(data: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename="f.bin")


def test_max_upload_bytes_defaults_to_50_mb(monkeypatch):
    monkeypatch.delenv("VISION_MAX_UPLOAD_BYTES", raising=False)

    assert max_upload_bytes() == DEFAULT_MAX_UPLOAD_BYTES == 50 * 1024 * 1024


def test_max_upload_bytes_reads_the_environment(monkeypatch):
    monkeypatch.setenv("VISION_MAX_UPLOAD_BYTES", "1234")

    assert max_upload_bytes() == 1234


@pytest.mark.parametrize("value", ["abc", "0", "-5"])
def test_max_upload_bytes_rejects_invalid_values(monkeypatch, value):
    monkeypatch.setenv("VISION_MAX_UPLOAD_BYTES", value)

    with pytest.raises(ValueError):
        max_upload_bytes()


@pytest.mark.asyncio
async def test_read_upload_limited_returns_content_within_limit():
    assert await read_upload_limited(_upload(b"0123456789"), max_bytes=10) == b"0123456789"


@pytest.mark.asyncio
async def test_read_upload_limited_rejects_oversized_upload():
    with pytest.raises(HTTPException) as exc:
        await read_upload_limited(_upload(b"0123456789X"), max_bytes=10)

    assert exc.value.status_code == 413


@pytest.fixture
def small_limit(monkeypatch):
    monkeypatch.setenv("VISION_MAX_UPLOAD_BYTES", "10")


def test_upload_sensorial_rejects_oversized_file(small_limit, monkeypatch, tmp_path):
    monkeypatch.setattr(gateway, "TEMP_UPLOAD_DIR", str(tmp_path))

    resp = TestClient(gateway.app).post("/upload_sensorial", files={"file": ("big.bin", b"x" * 11)})

    assert resp.status_code == 413
    assert not list(tmp_path.iterdir())


def test_memoria_aprender_rejects_oversized_file(small_limit):
    resp = TestClient(gateway.app).post("/api/memoria/aprender", files={"file": ("big.txt", b"x" * 11)})

    assert resp.status_code == 413
