import os
import subprocess
import sys

import pytest

from core.main import BrainstemWatchdog, build_child_env


def test_child_env_puts_project_root_first_on_pythonpath(tmp_path):
    env = build_child_env(str(tmp_path), base_env={"PYTHONPATH": "extra"}, dotenv_path=tmp_path / ".env")

    assert env["PYTHONPATH"].split(os.pathsep) == [str(tmp_path), "extra"]


def test_child_env_loads_dotenv_without_overriding_shell_values(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("OPENROUTER_API_KEY=from-file\nTAVILY_API_KEY=tavily-file\n", encoding="utf-8")

    env = build_child_env(str(tmp_path), base_env={"OPENROUTER_API_KEY": "from-shell"}, dotenv_path=dotenv)

    assert env["OPENROUTER_API_KEY"] == "from-shell"
    assert env["TAVILY_API_KEY"] == "tavily-file"


def test_child_env_forces_utf8_stdio(tmp_path):
    assert build_child_env(str(tmp_path), base_env={}, dotenv_path=tmp_path / ".env")["PYTHONIOENCODING"] == "utf-8"


@pytest.mark.asyncio
async def test_spawned_service_runs_from_project_root_and_imports_project_packages(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # the watchdog may be launched from any directory
    watchdog = BrainstemWatchdog()
    probe = tmp_path / "probe.py"
    probe.write_text("import os\nimport sentidos.seguridad_local\nprint(os.getcwd())\nprint('✅')\n", encoding="utf-8")

    proc = await watchdog._spawn(str(probe), [])
    out, err = await proc.communicate()

    assert proc.returncode == 0, err.decode("utf-8", errors="replace")
    cwd, emoji = out.decode("utf-8").split()
    assert os.path.samefile(cwd, watchdog.project_root)
    assert emoji == "✅"


def test_watchdog_logging_survives_characters_the_console_cannot_encode():
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONPATH": project_root}
    code = "import logging, core.main; logging.getLogger('Watchdog').info('[PERIFERICO-ERR] Loading weights: █████ ✅')"

    result = subprocess.run([sys.executable, "-c", code], capture_output=True, env=env, cwd=project_root, timeout=60)

    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert b"Logging error" not in result.stderr
    assert b"Loading weights" in result.stdout
