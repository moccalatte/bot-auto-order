#!/usr/bin/env python3
"""
Comprehensive Import Checker for bot-auto-order
Checks all Python files for import errors, missing functions, and circular dependencies.
"""

import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


class ImportChecker:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.imports: Dict[str, Set[str]] = {}
        self.exports: Dict[str, Set[str]] = {}

    def check_file(self, filepath: Path) -> bool:
        """Check a single Python file for import issues."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content, filename=str(filepath))
            self._extract_imports_and_exports(filepath, tree)
            return True
        except SyntaxError as e:
            self.errors.append(f"❌ SyntaxError in {filepath}: {e}")
            return False
        except Exception as e:
            self.errors.append(f"❌ Error parsing {filepath}: {e}")
            return False

    def _extract_imports_and_exports(self, filepath: Path, tree: ast.AST):
        """Extract imports and function definitions from AST."""
        relative_path = str(filepath.relative_to(self.root_dir))
        module_name = relative_path.replace("/", ".").replace(".py", "")

        # Track imports
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        import_name = alias.name
                        imports.add(f"{node.module}.{import_name}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)

        self.imports[module_name] = imports

        # Track exports (function and class definitions)
        exports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not node.name.startswith("_"):
                    exports.add(node.name)
            elif isinstance(node, ast.AsyncFunctionDef):
                if not node.name.startswith("_"):
                    exports.add(node.name)
            elif isinstance(node, ast.ClassDef):
                exports.add(node.name)

        self.exports[module_name] = exports

    def verify_imports(self):
        """Verify that all imported functions/classes exist."""
        for module_name, imports in self.imports.items():
            for imp in imports:
                parts = imp.split(".")

                # Check if importing from src.* modules
                if parts[0] == "src":
                    imported_module = ".".join(parts[:-1])
                    imported_name = parts[-1]

                    # Check if the module exists in our exports
                    if imported_module in self.exports:
                        if imported_name not in self.exports[imported_module]:
                            self.errors.append(
                                f"❌ {module_name} imports '{imported_name}' from '{imported_module}', "
                                f"but it's not defined there."
                            )

    def find_circular_imports(self) -> List[List[str]]:
        """Detect circular import dependencies."""

        def build_graph():
            graph = {}
            for module, imports in self.imports.items():
                graph[module] = set()
                for imp in imports:
                    parts = imp.split(".")
                    if parts[0] == "src":
                        imported_module = ".".join(parts[:-1])
                        graph[module].add(imported_module)
            return graph

        def find_cycles(graph, start, visited, path):
            visited.add(start)
            path.append(start)

            cycles = []
            if start in graph:
                for neighbor in graph[start]:
                    if neighbor not in visited:
                        cycles.extend(find_cycles(graph, neighbor, visited, path))
                    elif neighbor in path:
                        cycle_start = path.index(neighbor)
                        cycles.append(path[cycle_start:] + [neighbor])

            path.pop()
            return cycles

        graph = build_graph()
        all_cycles = []

        for node in graph:
            visited = set()
            cycles = find_cycles(graph, node, visited, [])
            for cycle in cycles:
                if cycle not in all_cycles:
                    all_cycles.append(cycle)

        return all_cycles

    def check_all_files(self):
        """Check all Python files in src directory."""
        src_dir = self.root_dir / "src"

        if not src_dir.exists():
            self.errors.append(f"❌ Source directory not found: {src_dir}")
            return

        python_files = list(src_dir.rglob("*.py"))
        print(f"📂 Checking {len(python_files)} Python files...")

        success_count = 0
        for filepath in python_files:
            if self.check_file(filepath):
                success_count += 1

        print(f"✅ Successfully parsed {success_count}/{len(python_files)} files")

        # Verify imports
        print("\n🔍 Verifying imports...")
        self.verify_imports()

        # Check for circular imports
        print("🔄 Checking for circular imports...")
        cycles = self.find_circular_imports()
        if cycles:
            for cycle in cycles:
                self.warnings.append(
                    f"⚠️  Circular import detected: {' -> '.join(cycle)}"
                )

    def print_report(self):
        """Print the final report."""
        print("\n" + "=" * 80)
        print("📊 IMPORT CHECKER REPORT")
        print("=" * 80)

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  {error}")
        else:
            print("\n✅ No errors found!")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  {warning}")

        # Summary
        print("\n" + "=" * 80)
        print("📈 SUMMARY:")
        print(f"  Modules analyzed: {len(self.exports)}")
        print(f"  Total exports: {sum(len(e) for e in self.exports.values())}")
        print(f"  Total imports: {sum(len(i) for i in self.imports.values())}")
        print(f"  Errors: {len(self.errors)}")
        print(f"  Warnings: {len(self.warnings)}")
        print("=" * 80)

        return len(self.errors) == 0


def main():
    """Main entry point."""
    # Get project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    print("🔧 Bot Auto-Order Import Checker")
    print(f"📁 Project root: {project_root}")
    print()

    checker = ImportChecker(str(project_root))
    checker.check_all_files()

    success = checker.print_report()

    if success:
        print("\n🎉 All import checks passed!")
        sys.exit(0)
    else:
        print("\n💥 Import check failed! Please fix the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
