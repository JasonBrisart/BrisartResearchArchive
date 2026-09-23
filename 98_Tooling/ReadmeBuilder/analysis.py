"""
Project analysis logic for ReadmeBuilder.
"""

from __future__ import annotations

import ast
from pathlib import Path

from constants import (
    MAX_CLASSES_PER_MODULE,
    MAX_ENTRYPOINTS,
    MAX_FUNCTIONS_PER_MODULE,
    MAX_IMPORT_SCAN_FILES,
    MAX_MODULE_SUMMARIES,
    PYTHON_STDLIB_APPROX,
)
from filesystem import safe_read_text


def clean_docstring_summary(docstring: str) -> str:
    """
    Convert a docstring into a short readable summary.
    """
    lines = [line.strip() for line in docstring.strip().splitlines() if line.strip()]

    if not lines:
        return ""

    summary = lines[0]

    if len(summary) < 20 and len(lines) > 1:
        summary = f"{summary} — {lines[1]}"

    return summary.strip()


def parse_python_file(path: Path) -> dict:
    """
    Parse a Python file for imports, docstrings, classes, functions, and entrypoint hints.
    """
    result = {
        "path": str(path),
        "imports": set(),
        "module_docstring": "",
        "classes": [],
        "functions": [],
        "has_main_guard": False,
        "uses_sys_argv": False,
        "uses_argparse": False,
        "uses_tkinter": False,
        "syntax_error": False,
    }

    text = safe_read_text(path)

    if not text:
        return result

    result["uses_sys_argv"] = "sys.argv" in text
    result["uses_argparse"] = "argparse" in text
    result["uses_tkinter"] = "tkinter" in text or "from tkinter" in text
    result["has_main_guard"] = '__name__ == "__main__"' in text or "__name__ == '__main__'" in text

    try:
        tree = ast.parse(text)
    except SyntaxError:
        result["syntax_error"] = True
        return result
    except Exception:
        return result

    docstring = ast.get_docstring(tree)

    if docstring:
        result["module_docstring"] = clean_docstring_summary(docstring)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[0]
                if name:
                    result["imports"].add(name)

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                name = node.module.split(".")[0]
                if name:
                    result["imports"].add(name)

        elif isinstance(node, ast.ClassDef):
            if len(result["classes"]) < MAX_CLASSES_PER_MODULE:
                result["classes"].append(node.name)

        elif isinstance(node, ast.FunctionDef):
            if len(result["functions"]) < MAX_FUNCTIONS_PER_MODULE:
                result["functions"].append(node.name)

    return result


def collect_python_analysis(root: Path, files: list[Path]) -> dict:
    """
    Collect Python analysis.
    """
    python_files = [path for path in files if path.suffix.lower() == ".py"]
    python_files = python_files[:MAX_IMPORT_SCAN_FILES]

    modules = []
    imports: set[str] = set()
    entrypoints = []

    for path in python_files:
        parsed = parse_python_file(path)
        imports.update(parsed["imports"])

        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path

        module = {
            "path": str(rel),
            "module_docstring": parsed["module_docstring"],
            "classes": parsed["classes"],
            "functions": parsed["functions"],
            "has_main_guard": parsed["has_main_guard"],
            "uses_sys_argv": parsed["uses_sys_argv"],
            "uses_argparse": parsed["uses_argparse"],
            "uses_tkinter": parsed["uses_tkinter"],
            "syntax_error": parsed["syntax_error"],
        }

        modules.append(module)

        name = path.name.lower()

        looks_like_entrypoint = (
            parsed["has_main_guard"]
            or name in {"main.py", "app.py", "run.py", "launcher.py", "gui_app.py"}
            or parsed["uses_sys_argv"]
            or parsed["uses_argparse"]
            or parsed["uses_tkinter"]
        )

        if looks_like_entrypoint:
            entrypoints.append(module)

    internal_modules = {
        path.stem
        for path in files
        if path.suffix.lower() == ".py"
    }

    standard_library_imports = sorted(
        name for name in imports
        if name in PYTHON_STDLIB_APPROX
    )

    possible_external_imports = sorted(
        name for name in imports
        if name not in PYTHON_STDLIB_APPROX and name not in internal_modules
    )

    internal_imports = sorted(
        name for name in imports
        if name in internal_modules
    )

    module_summaries = [
        module
        for module in modules
        if module["module_docstring"] or module["classes"] or module["functions"]
    ][:MAX_MODULE_SUMMARIES]

    return {
        "python_files_scanned": len(python_files),
        "all_imports": sorted(imports),
        "standard_library_imports": standard_library_imports,
        "possible_external_imports": possible_external_imports,
        "internal_imports": internal_imports,
        "entrypoints": entrypoints[:MAX_ENTRYPOINTS],
        "module_summaries": module_summaries,
        "uses_tkinter": any(module["uses_tkinter"] for module in modules),
        "uses_argparse": any(module["uses_argparse"] for module in modules),
        "uses_sys_argv": any(module["uses_sys_argv"] for module in modules),
        "has_main_guard": any(module["has_main_guard"] for module in modules),
    }


def detect_project_traits(files: list[Path], python_analysis: dict) -> dict:
    """
    Detect project traits.
    """
    file_names = {path.name.lower() for path in files}
    suffixes = {path.suffix.lower() for path in files}

    return {
        "uses_python": ".py" in suffixes,
        "uses_json": ".json" in suffixes,
        "uses_csv": ".csv" in suffixes,
        "uses_markdown": ".md" in suffixes,
        "uses_web_files": bool({".html", ".css", ".js", ".ts", ".jsx", ".tsx"} & suffixes),
        "has_gui_signals": python_analysis.get("uses_tkinter", False),
        "has_cli_signals": python_analysis.get("uses_argparse", False)
        or python_analysis.get("uses_sys_argv", False)
        or python_analysis.get("has_main_guard", False),
        "has_requirements_file": "requirements.txt" in file_names,
        "has_pyproject": "pyproject.toml" in file_names,
        "has_package_json": "package.json" in file_names,
        "has_license": any(name in file_names for name in {"license", "license.md", "license.txt"}),
        "has_readme": any(name == "readme.md" for name in file_names),
    }


def infer_project_type(traits: dict) -> str:
    """
    Infer a GitHub-friendly project type.
    """
    if traits.get("has_gui_signals") and traits.get("has_cli_signals"):
        return "Python utility with GUI and command-line support"

    if traits.get("has_gui_signals"):
        return "Python desktop utility"

    if traits.get("has_cli_signals"):
        return "Python command-line utility"

    if traits.get("uses_web_files"):
        return "web-oriented project"

    if traits.get("uses_python"):
        return "Python project"

    return "software project"


def infer_value_statement(project_name: str, traits: dict) -> str:
    """
    Build a GitHub-friendly value statement.
    """
    project_type = infer_project_type(traits)

    if traits.get("has_gui_signals") and traits.get("has_cli_signals"):
        return (
            f"{project_name} is a lightweight {project_type} designed to make a "
            "specific local workflow easier to run, document, or share."
        )

    if traits.get("has_gui_signals"):
        return (
            f"{project_name} is a lightweight {project_type} designed for users who "
            "prefer a simple graphical interface."
        )

    if traits.get("has_cli_signals"):
        return (
            f"{project_name} is a lightweight {project_type} designed for repeatable "
            "local workflows."
        )

    return (
        f"{project_name} is a {project_type} with detected project files, structure, "
        "and source-code components."
    )


def build_feature_list(traits: dict, python_analysis: dict) -> list[str]:
    """
    Build GitHub-facing feature bullets.
    """
    features: list[str] = []

    if traits.get("has_gui_signals"):
        features.append("GUI support detected")

    if traits.get("has_cli_signals"):
        features.append("Command-line usage support detected")

    if traits.get("uses_python"):
        features.append("Python-based implementation")

    if traits.get("uses_json"):
        features.append("JSON configuration, data, or metadata files detected")

    if traits.get("uses_csv"):
        features.append("CSV data/input/output files detected")

    if traits.get("uses_markdown"):
        features.append("Markdown documentation detected")

    if traits.get("has_requirements_file"):
        features.append("requirements.txt dependency file detected")

    if traits.get("has_pyproject"):
        features.append("pyproject.toml project configuration detected")

    if python_analysis.get("entrypoints"):
        features.append("Likely runnable entry point detected")

    if not features:
        features.append("Project files detected and summarized")

    return features


def build_primary_entrypoint(python_analysis: dict) -> str:
    """
    Return the most likely entrypoint path.
    """
    entrypoints = python_analysis.get("entrypoints", [])

    if not entrypoints:
        return ""

    priority_names = [
        "main.py",
        "app.py",
        "launcher.py",
        "run.py",
        "gui_app.py",
    ]

    for priority in priority_names:
        for entry in entrypoints:
            if Path(entry["path"]).name.lower() == priority:
                return entry["path"]

    return entrypoints[0]["path"]