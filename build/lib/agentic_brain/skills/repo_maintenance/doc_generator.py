# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Documentation Generator - Auto-generates docs from code.

Scans modules, extracts docstrings, generates markdown docs.
"""

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class ModuleDoc:
    """Documentation for a module."""

    name: str
    path: str
    docstring: str = ""
    classes: list[dict[str, Any]] = field(default_factory=list)
    functions: list[dict[str, Any]] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Convert to markdown documentation."""
        lines = [f"# {self.name}", ""]

        if self.docstring:
            lines.extend([self.docstring, ""])

        if self.classes:
            lines.append("## Classes")
            for cls in self.classes:
                lines.append(f"\n### `{cls['name']}`")
                if cls.get("docstring"):
                    lines.append(f"\n{cls['docstring']}")
                if cls.get("methods"):
                    lines.append("\n**Methods:**")
                    for method in cls["methods"]:
                        sig = method.get("signature", "")
                        lines.append(f"- `{method['name']}{sig}`")

        if self.functions:
            lines.append("\n## Functions")
            for func in self.functions:
                sig = func.get("signature", "")
                lines.append(f"\n### `{func['name']}{sig}`")
                if func.get("docstring"):
                    lines.append(f"\n{func['docstring']}")

        return "\n".join(lines)


@dataclass
class DocReport:
    """Documentation generation report."""

    total_modules: int = 0
    documented_modules: int = 0
    undocumented: list[str] = field(default_factory=list)
    generated_files: list[str] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        if self.total_modules == 0:
            return 100.0
        return (self.documented_modules / self.total_modules) * 100


class DocGenerator:
    """
    Auto-generates documentation from Python source.

    Usage:
        gen = DocGenerator()
        report = gen.generate()
        gen.write_docs("docs/api/")
    """

    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = (
            Path(repo_path)
            if repo_path
            else Path(__file__).parent.parent.parent.parent.parent
        )
        self.src_path = self.repo_path / "src"
        self.docs: list[ModuleDoc] = []

    def _parse_module(self, file_path: Path) -> Optional[ModuleDoc]:
        """Parse a Python module and extract documentation."""
        try:
            content = file_path.read_text()
            tree = ast.parse(content)

            # Get module docstring
            docstring = ast.get_docstring(tree) or ""

            # Get module name
            rel_path = file_path.relative_to(self.src_path)
            module_name = str(rel_path).replace("/", ".").replace(".py", "")

            classes = []
            functions = []

            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef):
                    cls_doc = {
                        "name": node.name,
                        "docstring": ast.get_docstring(node) or "",
                        "methods": [],
                    }
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            cls_doc["methods"].append(
                                {
                                    "name": item.name,
                                    "docstring": ast.get_docstring(item) or "",
                                    "signature": self._get_signature(item),
                                }
                            )
                    classes.append(cls_doc)

                elif isinstance(node, ast.FunctionDef):
                    functions.append(
                        {
                            "name": node.name,
                            "docstring": ast.get_docstring(node) or "",
                            "signature": self._get_signature(node),
                        }
                    )

            return ModuleDoc(
                name=module_name,
                path=str(file_path.relative_to(self.repo_path)),
                docstring=docstring,
                classes=classes,
                functions=functions,
            )
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return None

    def _get_signature(self, node: ast.FunctionDef) -> str:
        """Extract function signature."""
        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        return f"({', '.join(args)})"

    def scan(self) -> DocReport:
        """Scan all modules and extract documentation."""
        self.docs = []
        files = list(self.src_path.rglob("*.py"))
        undocumented = []

        for f in files:
            if f.name.startswith("_") and f.name != "__init__.py":
                continue
            doc = self._parse_module(f)
            if doc:
                self.docs.append(doc)
                if not doc.docstring:
                    undocumented.append(doc.path)

        return DocReport(
            total_modules=len(self.docs),
            documented_modules=len(self.docs) - len(undocumented),
            undocumented=undocumented,
        )

    def generate(self, output_dir: Optional[str] = None) -> DocReport:
        """Generate markdown documentation for all modules."""
        report = self.scan()

        out_path = Path(output_dir) if output_dir else self.repo_path / "docs" / "api"

        out_path.mkdir(parents=True, exist_ok=True)

        for doc in self.docs:
            # Create output file
            doc_file = out_path / f"{doc.name.replace('.', '_')}.md"
            doc_file.write_text(doc.to_markdown())
            report.generated_files.append(str(doc_file.relative_to(self.repo_path)))

        # Generate index
        index_content = ["# API Reference", ""]
        for doc in sorted(self.docs, key=lambda d: d.name):
            link = f"{doc.name.replace('.', '_')}.md"
            index_content.append(f"- [{doc.name}]({link})")

        (out_path / "index.md").write_text("\n".join(index_content))

        return report
