"""Check Python import direction; pure static analysis, no application imports."""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "apps" / "api" / "src"


def imported_names(tree: ast.AST, module: str, is_package: bool) -> list[str]:
    package = module if is_package else module.rpartition(".")[0]
    result = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                prefix = ".".join(parts[: len(parts) - node.level + 1])
                target = ".".join(part for part in (prefix, node.module) if part)
            else:
                target = node.module or ""
            result.extend(f"{target}.{alias.name}" for alias in node.names)
    return result


def violations(source: str, module: str, *, is_package: bool = False) -> list[str]:
    errors = set()
    parts = module.split(".")
    own_module = parts[2] if len(parts) > 2 and parts[:2] == ["factoryflow", "modules"] else None
    pure = ".domain." in f"{module}." or module.startswith("factoryflow.kernel.")
    for dependency in imported_names(ast.parse(source), module, is_package):
        dep = dependency.split(".")
        internal = dependency.startswith("factoryflow.")
        if pure:
            allowed_internal = dependency.startswith("factoryflow.kernel") or (
                own_module is not None
                and dependency.startswith(f"factoryflow.modules.{own_module}.domain")
            )
            if (internal and not allowed_internal) or (
                not internal and dep[0] not in sys.stdlib_module_names
            ):
                errors.add(f"pure domain depends on {dependency}")
        if own_module and dep[:2] == ["factoryflow", "modules"] and len(dep) >= 3:
            if dep[2] != own_module and (len(dep) < 4 or dep[3] != "public"):
                errors.add(f"cross-module private import: {dependency}")
        if own_module and ".application." in f"{module}.":
            if ".adapters" in dependency or dependency.startswith("factoryflow.platform"):
                errors.add(f"application depends on adapter: {dependency}")
        if module.startswith("factoryflow.platform.") and dependency.startswith(
            "factoryflow.modules"
        ):
            errors.add(f"platform depends on business module: {dependency}")
    return sorted(errors)


def check_tree(root: Path = SOURCE) -> list[str]:
    errors = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root).with_suffix("")
        is_package = relative.name == "__init__"
        module = ".".join(relative.parts[:-1] if is_package else relative.parts)
        errors.extend(
            f"{path.relative_to(root)}: {error}"
            for error in violations(path.read_text(encoding="utf-8"), module, is_package=is_package)
        )
    return errors


if __name__ == "__main__":
    found = check_tree()
    print("\n".join(found) if found else "Python architecture boundaries pass.")
    raise SystemExit(bool(found))
