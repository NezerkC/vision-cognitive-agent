"""Provider credentials stored in the project .env, as exposed to the GUI.

Secrets never leave the server in clear text: reads return masked values, and writes are limited to the known
provider keys so the endpoint cannot be used to set arbitrary environment variables.
"""

import os
from pathlib import Path

from dotenv import dotenv_values, set_key

CREDENTIAL_KEYS = (
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "LMSTUDIO_API_KEY",
    "TAVILY_API_KEY",
)
MASK = "••••"
_MIN_LENGTH_TO_SHOW_SUFFIX = 12


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) < _MIN_LENGTH_TO_SHOW_SUFFIX:
        return MASK
    return MASK + value[-4:]


def leer_credenciales_enmascaradas(env_path: str | os.PathLike) -> dict[str, str]:
    values = dotenv_values(env_path) if Path(env_path).exists() else {}
    return {key: mask_secret(values.get(key) or "") for key in CREDENTIAL_KEYS}


def guardar_credencial(env_path: str | os.PathLike, clave: str, valor: str) -> None:
    if clave not in CREDENTIAL_KEYS:
        raise ValueError(f"Credencial desconocida: {clave!r}.")
    if not valor or valor.startswith(MASK):
        raise ValueError("Ingresá la key completa; el valor enmascarado no se guarda.")

    env_file = Path(env_path)
    if not env_file.exists():
        env_file.write_text("# Vision OS — Environment Configuration\n", encoding="utf-8")
    set_key(str(env_file), clave, valor)
