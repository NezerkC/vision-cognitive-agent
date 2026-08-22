import shutil
from pathlib import Path

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
