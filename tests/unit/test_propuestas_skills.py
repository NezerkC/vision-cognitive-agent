import json
import os

import pytest

import cognitivo.propuestas_skills as propuestas
from cognitivo.protocolo_intriga import ProtocoloIntriga

VALID_TOOL = '''from langchain_core.tools import tool
import subprocess


@tool
def git_status(path: str) -> str:
    """Return git status for a repository."""
    return subprocess.run(["git", "status"], cwd=path, capture_output=True, text=True).stdout
'''

MOCK_RESPONSE = '"""\nMock response for git_tool\n"""'

SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cognitivo", "skills")


class FakeWriter:
    def __init__(self):
        self.events = []

    def write(self, data: bytes):
        self.events.append(json.loads(data.decode("utf-8")))

    async def drain(self):
        pass


@pytest.fixture
def proposals_dir(tmp_path, monkeypatch):
    target = tmp_path / "skills_propuestas"
    monkeypatch.setattr(propuestas, "PROPOSALS_DIR", str(target))
    return target


@pytest.mark.parametrize("name", ["git", "docker-compose", "kubectl", "go"])
def test_validate_cli_name_accepts_plain_names(name):
    assert propuestas.validate_cli_name(name) == name


@pytest.mark.parametrize("name", ["", "..", "../evil", "..\\evil", "Git", "a/b", "x" * 40, None])
def test_validate_cli_name_rejects_unsafe_names(name):
    with pytest.raises(ValueError):
        propuestas.validate_cli_name(name)


def test_is_valid_tool_code_requires_a_tool_decorated_function():
    assert propuestas.is_valid_tool_code(VALID_TOOL)
    assert not propuestas.is_valid_tool_code(MOCK_RESPONSE)
    assert not propuestas.is_valid_tool_code("def broken(:\n    pass")
    assert not propuestas.is_valid_tool_code("def plain():\n    return 1\n")


def test_save_proposal_writes_a_non_importable_file_outside_the_package(proposals_dir):
    path = propuestas.save_proposal("git", VALID_TOOL)

    assert path == str(proposals_dir / "git_tool.py.txt")
    assert (proposals_dir / "git_tool.py.txt").read_text(encoding="utf-8") == VALID_TOOL
    assert propuestas.has_proposal("git")
    assert not propuestas.has_proposal("docker")


@pytest.mark.asyncio
async def test_capacitacion_response_becomes_a_quarantined_proposal(proposals_dir):
    writer = FakeWriter()

    await ProtocoloIntriga().handle_llm_response("capacitacion-tool-git-1700000000", VALID_TOOL, writer)

    assert (proposals_dir / "git_tool.py.txt").exists()
    assert not os.path.exists(os.path.join(SKILLS_DIR, "git_tool.py"))
    topics = [e["topic"] for e in writer.events]
    assert "canal.sistema.anuncios" in topics
    memory = next(e for e in writer.events if e["topic"] == "canal.memoria")
    assert "revisión" in memory["data"]["text"]


@pytest.mark.asyncio
async def test_capacitacion_response_with_hyphenated_cli_name(proposals_dir):
    await ProtocoloIntriga().handle_llm_response(
        "capacitacion-tool-docker-compose-1700000000", VALID_TOOL, FakeWriter()
    )

    assert (proposals_dir / "docker-compose_tool.py.txt").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [MOCK_RESPONSE, "def broken(:\n    pass"])
async def test_capacitacion_rejects_code_that_is_not_a_tool(proposals_dir, response):
    writer = FakeWriter()

    await ProtocoloIntriga().handle_llm_response("capacitacion-tool-git-1700000000", response, writer)

    assert not proposals_dir.exists() or not list(proposals_dir.iterdir())
    assert all(e["topic"] != "canal.memoria" for e in writer.events)


@pytest.mark.asyncio
async def test_capacitacion_rejects_unsafe_cli_names(proposals_dir, tmp_path):
    writer = FakeWriter()

    await ProtocoloIntriga().handle_llm_response("capacitacion-tool-..\\..\\evil-1700000000", VALID_TOOL, writer)
    await ProtocoloIntriga().iniciar_protocolo_capacitacion("../evil", writer)

    assert not list(tmp_path.rglob("*evil*"))
    assert writer.events == []


@pytest.mark.asyncio
async def test_cli_scan_skips_clis_with_a_pending_proposal(proposals_dir, monkeypatch):
    from cognitivo import contexto_derecho

    propuestas.save_proposal("git", VALID_TOOL)
    monkeypatch.setattr(
        contexto_derecho.shutil, "which", lambda cli: f"C:/bin/{cli}.exe" if cli in ("git", "npm") else None
    )
    writer = FakeWriter()

    await contexto_derecho.ContextoDerecho().scan_and_trigger_training(writer)

    assert [e["data"]["cli_name"] for e in writer.events] == ["npm"]


def test_package_has_no_generated_tool_modules():
    generated = {f"{n}_tool.py" for n in ("cargo", "docker", "gcloud", "git", "go", "kubectl", "npm", "pip", "python")}

    assert not generated & set(os.listdir(SKILLS_DIR))
