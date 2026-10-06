import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import sentidos.sistema_periferico as gateway
from sentidos.sistema_periferico import build_dir_tree


def test_build_dir_tree():
    temp_dir = Path(__file__).parent.parent / "temp_test_workspace"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        subfolder = temp_dir / "subfolder"
        subfolder.mkdir()
        file1 = temp_dir / "main.py"
        file1.write_text("print('hello')", encoding="utf-8")
        file2 = subfolder / "utils.py"
        file2.write_text("def add(a,b): return a+b", encoding="utf-8")

        tree = build_dir_tree(str(temp_dir))
        assert len(tree) == 2
        names = [node["name"] for node in tree]
        assert "main.py" in names
        assert "subfolder" in names

        subnode = next(node for node in tree if node["name"] == "subfolder")
        assert subnode["is_dir"] is True
        assert len(subnode["children"]) == 1
        assert subnode["children"][0]["name"] == "utils.py"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    (ws / "src").mkdir(parents=True)
    (ws / "src" / "needle_unique_zq.py").write_text("x = 1", encoding="utf-8")
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "needle_unique_zq_outside.py").write_text("y = 2", encoding="utf-8")
    monkeypatch.setattr(gateway, "_active_workspace", gateway.PROJECT_ROOT)
    return ws


@pytest.fixture
def client():
    return TestClient(gateway.app)


def test_open_workspace_sets_the_active_workspace(client, workspace):
    resp = client.post("/api/workspace/open", json={"path": str(workspace)})

    assert resp.status_code == 200
    assert [n["name"] for n in resp.json()["tree"]] == ["src"]
    assert os.path.samefile(client.get("/api/workspace/tree").json()["workspace_path"], workspace)


def test_open_workspace_rejects_missing_path(client, workspace):
    resp = client.post("/api/workspace/open", json={"path": str(workspace / "nope")})

    assert resp.status_code == 404
    assert gateway._active_workspace == gateway.PROJECT_ROOT


def test_open_workspace_rejects_files_and_filesystem_roots(client, workspace):
    file_path = workspace / "src" / "needle_unique_zq.py"
    root = os.path.abspath(os.sep)

    assert client.post("/api/workspace/open", json={"path": str(file_path)}).status_code == 400
    assert client.post("/api/workspace/open", json={"path": root}).status_code == 400


def test_tree_rejects_paths_outside_the_active_workspace(client, workspace, tmp_path):
    client.post("/api/workspace/open", json={"path": str(workspace)})

    assert client.get("/api/workspace/tree", params={"path": str(tmp_path / "outside")}).status_code == 403
    assert client.get("/api/workspace/tree", params={"path": str(workspace / ".." / "outside")}).status_code == 403


def test_tree_returns_404_instead_of_falling_back_to_project_root(client, workspace):
    client.post("/api/workspace/open", json={"path": str(workspace)})

    assert client.get("/api/workspace/tree", params={"path": str(workspace / "missing")}).status_code == 404


def test_tree_lists_subfolders_inside_the_active_workspace(client, workspace):
    client.post("/api/workspace/open", json={"path": str(workspace)})

    resp = client.get("/api/workspace/tree", params={"path": str(workspace / "src")})

    assert resp.status_code == 200
    assert [n["name"] for n in resp.json()["tree"]] == ["needle_unique_zq.py"]


def test_file_search_only_covers_the_active_workspace(client, workspace):
    client.post("/api/workspace/open", json={"path": str(workspace)})

    results = client.get("/api/archivos", params={"q": "needle_unique_zq"}).json()

    assert [r["nombre"] for r in results] == ["needle_unique_zq.py"]
    assert results[0]["ruta_relativa"] == os.path.join("src", "needle_unique_zq.py")


@pytest.mark.parametrize(
    "repo_url",
    [
        "--upload-pack=calc.exe",
        "-c core.sshCommand=calc.exe",
        "ext::sh -c calc.exe",
        "file:///C:/Windows",
        "https://github.com/owner/..",
    ],
)
def test_clone_rejects_unsafe_repo_urls_without_running_git(client, monkeypatch, repo_url):
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("git must not run for an unsafe URL")

    monkeypatch.setattr(gateway.asyncio, "create_subprocess_exec", fail_if_called)

    resp = client.post("/api/workspace/clone_git", json={"repo_url": repo_url})

    assert resp.status_code == 400
