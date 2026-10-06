"""Quarantine for tool code written by the LLM during auto-training (Protocolo de Capacitación).

Generated code is never written into the `cognitivo` package: it goes to memoria_activa/skills_propuestas as
`<cli>_tool.py.txt`, which Python cannot import, and waits there for a human to review it and move it into place.
Only code that parses and defines at least one `@tool` function is kept, so mock or garbage replies are dropped.
"""

import ast
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROPOSALS_DIR = os.path.join(PROJECT_ROOT, "memoria_activa", "skills_propuestas")

_CLI_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")


def validate_cli_name(name: object) -> str:
    """Return the CLI name if it is a plain lowercase command name, else raise ValueError."""
    if not isinstance(name, str) or not _CLI_NAME.match(name):
        raise ValueError(f"Nombre de CLI inválido: {name!r}")
    return name


def is_valid_tool_code(code: str) -> bool:
    """True when the code parses and defines at least one function decorated with `tool`."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(_is_tool(d) for d in node.decorator_list)
        for node in ast.walk(tree)
    )


def _is_tool(decorator: ast.expr) -> bool:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(target, ast.Name):
        return target.id == "tool"
    return isinstance(target, ast.Attribute) and target.attr == "tool"


def proposal_path(cli_name: str) -> str:
    return os.path.join(PROPOSALS_DIR, f"{validate_cli_name(cli_name)}_tool.py.txt")


def has_proposal(cli_name: str) -> bool:
    return os.path.exists(proposal_path(cli_name))


def save_proposal(cli_name: str, code: str) -> str:
    """Write a reviewed-later tool proposal and return its path."""
    path = proposal_path(cli_name)
    os.makedirs(PROPOSALS_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    return path
