"""
Project scanning and entry point detection for AutoExeBuilder.
"""

from __future__ import annotations

import ast
from pathlib import Path

from constants import ENTRYPOINT_PRIORITY_NAMES, PYTHON_STDLIB_HINTS
from filesystem import iter_project_files, safe_read_text


def parse_python_file(path: Path) -> dict:
    """
    Parse a Python file for executable/build-relevant signals.
    """
    text = safe_read_text(path)

    result = {
        "path": str(path),
        "module_docstring": "",
        "imports": set(),
        "functions": [],
        "classes": [],
        "has_main_guard": False,
        "uses_tkinter": False,
        "uses_argparse": False,
        "uses_sys_argv": False,
        "syntax_error": False,
        "score": 0,
        "reasons": [],
    }

    if not text:
        return result

    result["has_main_guard"] = (
        '__name__ == "__main__"' in text
        or "__name__ == '__main__'" in text
    )
    result["uses_tkinter"] = "tkinter" in text or "from tkinter" in text
    result["uses_argparse"] = "argparse" in text
    result["uses_sys_argv"] = "sys.argv" in text

    try:
        tree = ast.parse(text)
    except SyntaxError:
        result["syntax_error"] = True
        return result
    except Exception:
        return result

    docstring = ast.get_docstring(tree)
    if docstring:
        result["module_docstring"] = docstring.strip().splitlines()[0].strip()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[0]
                if name:
                    result["imports"].add(name)

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                name = node.module.split(".")[0]
                result["imports"].add(name)

        elif isinstance(node, ast.FunctionDef):
            if len(result["functions"]) < 20:
                result["functions"].append(node.name)

        elif isinstance(node, ast.ClassDef):
            if len(result["classes"]) < 20:
                result["classes"].append(node.name)

    return result


def score_entrypoint(path: Path, parsed: dict) -> tuple[int, list[str]]:
    """
    Score a Python file as a likely app entry point.
    """
    score = 0
    reasons: list[str] = []

    name = path.name.lower()

    if name in ENTRYPOINT_PRIORITY_NAMES:
        score += 40
        reasons.append(f"priority filename: {path.name}")

    if parsed.get("has_main_guard"):
        score += 35
        reasons.append("contains __main__ guard")

    if parsed.get("uses_sys_argv"):
        score += 20
        reasons.append("uses sys.argv")

    if parsed.get("uses_argparse"):
        score += 20
        reasons.append("uses argparse")

    if parsed.get("uses_tkinter"):
        score += 20
        reasons.append("uses tkinter")

    launcher_words = ["main", "app", "run", "launcher", "gui", "builder"]
    if any(word in name for word in launcher_words):
        score += 10
        reasons.append("filename suggests runnable app")

    if parsed.get("syntax_error"):
        score -= 100
        reasons.append("syntax error detected")

    return score, reasons


def scan_project(project_root: Path) -> dict:
    """
    Scan a project folder and return build-relevant metadata.
    """
    files = iter_project_files(project_root)
    python_files = [path for path in files if path.suffix.lower() == ".py"]

    modules: list[dict] = []
    entrypoints: list[dict] = []
    imports: set[str] = set()

    internal_module_names = {path.stem for path in python_files}

    for path in python_files:
        parsed = parse_python_file(path)
        imports.update(parsed["imports"])

        try:
            relative_path = str(path.relative_to(project_root)).replace("\\", "/")
        except ValueError:
            relative_path = str(path)

        score, reasons = score_entrypoint(path, parsed)

        module_info = {
            "path": relative_path,
            "name": path.name,
            "module_docstring": parsed["module_docstring"],
            "imports": sorted(parsed["imports"]),
            "functions": parsed["functions"],
            "classes": parsed["classes"],
            "has_main_guard": parsed["has_main_guard"],
            "uses_tkinter": parsed["uses_tkinter"],
            "uses_argparse": parsed["uses_argparse"],
            "uses_sys_argv": parsed["uses_sys_argv"],
            "syntax_error": parsed["syntax_error"],
            "entrypoint_score": score,
            "entrypoint_reasons": reasons,
        }

        modules.append(module_info)

        if score > 0:
            entrypoints.append(module_info)

    entrypoints.sort(key=lambda item: item["entrypoint_score"], reverse=True)

    possible_external_imports = sorted(
        name
        for name in imports
        if name not in PYTHON_STDLIB_HINTS
        and name not in internal_module_names
    )

    return {
        "project_root": str(project_root),
        "files_scanned": len(files),
        "python_files_scanned": len(python_files),
        "modules": modules,
        "entrypoints": entrypoints,
        "suggested_entrypoint": entrypoints[0]["path"] if entrypoints else "",
        "uses_tkinter": any(module["uses_tkinter"] for module in modules),
        "uses_argparse": any(module["uses_argparse"] for module in modules),
        "uses_sys_argv": any(module["uses_sys_argv"] for module in modules),
        "possible_external_imports": possible_external_imports,
    }


def get_entrypoint_options(scan: dict) -> list[str]:
    """
    Return possible entry point paths.
    """
    options = [entry["path"] for entry in scan.get("entrypoints", [])]

    if options:
        return options

    modules = scan.get("modules", [])
    return [module["path"] for module in modules]