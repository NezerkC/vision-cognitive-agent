import subprocess

import pytest

import cognitivo.gestor_llamacpp as gestor


def _smi(output: str):
    def check_output(cmd, **kwargs):
        assert cmd[0] == "nvidia-smi"
        return output

    return check_output


def test_reads_the_real_gpu_from_nvidia_smi(monkeypatch):
    monkeypatch.setattr(gestor.subprocess, "check_output", _smi("NVIDIA GeForce RTX 4070, 6144, 12288, 61\n"))

    gpu = gestor.leer_gpu_nvidia()

    assert gpu == {
        "gpuName": "NVIDIA GeForce RTX 4070",
        "vramUsedGb": 6.0,
        "vramTotalGb": 12.0,
        "vramPercent": 50.0,
        "gpuTemp": 61,
    }


def test_missing_nvidia_smi_means_no_gpu_data(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("nvidia-smi")

    monkeypatch.setattr(gestor.subprocess, "check_output", missing)

    assert gestor.leer_gpu_nvidia() is None


@pytest.mark.parametrize("output", ["", "garbage\n", "NVIDIA X, [N/A], 12288, 61\n"])
def test_unparseable_nvidia_smi_output_means_no_gpu_data(monkeypatch, output):
    monkeypatch.setattr(gestor.subprocess, "check_output", _smi(output))

    assert gestor.leer_gpu_nvidia() is None


def test_telemetry_reports_null_instead_of_made_up_values(monkeypatch):
    def missing(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "nvidia-smi")

    monkeypatch.setattr(gestor.subprocess, "check_output", missing)
    monkeypatch.setattr(gestor, "leer_temperatura_cpu", lambda: None)

    telemetry = gestor.obtener_telemetria_sistema()

    for key in ("gpuName", "vramUsedGb", "vramTotalGb", "vramPercent", "gpuTemp", "cpuTemp"):
        assert telemetry[key] is None, key
    assert telemetry["ramTotalGb"] > 0


def test_cpu_temperature_comes_from_sensors_when_available(monkeypatch):
    class Reading:
        current = 57.5

    monkeypatch.setattr(gestor.psutil, "sensors_temperatures", lambda: {"coretemp": [Reading()]}, raising=False)

    assert gestor.leer_temperatura_cpu() == 57.5


def test_cpu_temperature_is_unknown_without_sensors(monkeypatch):
    monkeypatch.delattr(gestor.psutil, "sensors_temperatures", raising=False)

    assert gestor.leer_temperatura_cpu() is None


def test_gateway_reports_the_detected_gpu_name(monkeypatch):
    import sentidos.sistema_periferico as gateway

    monkeypatch.setattr(gateway, "obtener_telemetria_sistema", lambda: {"gpuName": "NVIDIA GeForce RTX 4070"})

    payload = gateway.construir_payload_telemetria()

    assert payload["data"]["gpu_name"] == "NVIDIA GeForce RTX 4070"
    assert payload["data"]["telemetry"]["gpuName"] == "NVIDIA GeForce RTX 4070"
