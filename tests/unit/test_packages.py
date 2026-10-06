import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run(code: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": ROOT}
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, timeout=300)


def test_memoria_package_wins_over_the_cognitivo_memoria_module():
    """llm_router puts cognitivo/ on sys.path; cognitivo/memoria.py must not shadow the memoria package."""
    code = (
        "import importlib.util, os, sys\n"
        "sys.path.append(os.path.join(os.getcwd(), 'cognitivo'))\n"
        "spec = importlib.util.find_spec('memoria')\n"
        "sys.exit(0 if spec.submodule_search_locations else 1)\n"
    )
    assert _run(code).returncode == 0


def test_in_process_orchestrator_is_importable():
    result = _run("import core.orchestrator")

    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")[-1500:]
