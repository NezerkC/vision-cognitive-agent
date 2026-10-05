import pytest
from dotenv import dotenv_values

from sentidos.credenciales import CREDENTIAL_KEYS, guardar_credencial, leer_credenciales_enmascaradas


def test_leer_masks_secret_values(tmp_path):
    env = tmp_path / ".env"
    # Deliberately not key-shaped, so secret scanners and history redaction leave the fixture alone.
    env.write_text("OPENROUTER_API_KEY=test-openrouter-key-1234567890\nTAVILY_API_KEY=\n", encoding="utf-8")

    creds = leer_credenciales_enmascaradas(env)

    assert creds["OPENROUTER_API_KEY"] == "••••7890"
    assert creds["TAVILY_API_KEY"] == ""
    assert set(creds) == set(CREDENTIAL_KEYS)


def test_leer_fully_masks_short_values(tmp_path):
    env = tmp_path / ".env"
    env.write_text("LMSTUDIO_API_KEY=abc123\n", encoding="utf-8")

    assert leer_credenciales_enmascaradas(env)["LMSTUDIO_API_KEY"] == "••••"


def test_leer_without_env_file_returns_empty_values(tmp_path):
    assert leer_credenciales_enmascaradas(tmp_path / ".env") == dict.fromkeys(CREDENTIAL_KEYS, "")


def test_guardar_persists_known_key(tmp_path):
    env = tmp_path / ".env"

    guardar_credencial(env, "OPENROUTER_API_KEY", "sk-or-v1-new")

    assert dotenv_values(env)["OPENROUTER_API_KEY"] == "sk-or-v1-new"


@pytest.mark.parametrize("clave", ["PATH", "OPENROUTER_API_KEY\nPATH", ""])
def test_guardar_rejects_unknown_keys(tmp_path, clave):
    with pytest.raises(ValueError):
        guardar_credencial(tmp_path / ".env", clave, "x")


def test_guardar_refuses_masked_placeholder_and_keeps_real_secret(tmp_path):
    env = tmp_path / ".env"
    env.write_text("OPENROUTER_API_KEY=real-secret-value\n", encoding="utf-8")

    with pytest.raises(ValueError):
        guardar_credencial(env, "OPENROUTER_API_KEY", "••••alue")

    assert dotenv_values(env)["OPENROUTER_API_KEY"] == "real-secret-value"
