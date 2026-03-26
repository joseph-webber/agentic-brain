#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Example 38: RAG Code Repository Assistant

An AI assistant for understanding and navigating codebases:
- Multi-language code parsing (Python, JavaScript, Java, TypeScript)
- Function/class/module extraction
- Dependency graph analysis
- Natural language code search
- Documentation generation
- Code explanation

Key RAG features demonstrated:
- Code-aware chunking (preserving functions/classes)
- AST-based extraction
- Symbol indexing
- Hybrid search (semantic + exact match)
- Context-aware retrieval (imports, dependencies)
- Evaluation metrics

Demo: Sample codebase with common patterns

Usage:
    python examples/38_rag_codebase.py
    python examples/38_rag_codebase.py --demo

Requirements:
    pip install agentic-brain sentence-transformers
    pip install tree-sitter tree-sitter-python tree-sitter-javascript
"""

import asyncio
import hashlib
import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Generator, Optional
import math

# Try imports
try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class CodeRAGConfig:
    """Configuration for code RAG pipeline."""

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # Code chunking
    max_function_size: int = 2000
    max_class_size: int = 5000
    include_docstrings: bool = True
    include_comments: bool = True

    # Retrieval
    top_k: int = 10
    rerank_top_k: int = 5
    similarity_threshold: float = 0.25

    # Language support
    supported_languages: tuple = ("python", "javascript", "typescript", "java", "go")


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS AND DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════


class Language(Enum):
    """Supported programming languages."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    CPP = "cpp"
    CSHARP = "csharp"
    UNKNOWN = "unknown"


class CodeElementType(Enum):
    """Types of code elements."""

    FILE = "file"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    CONSTANT = "constant"
    IMPORT = "import"
    INTERFACE = "interface"
    ENUM = "enum"
    DECORATOR = "decorator"
    COMMENT = "comment"
    DOCSTRING = "docstring"


@dataclass
class CodeElement:
    """A code element (function, class, etc.)."""

    id: str
    name: str
    element_type: CodeElementType
    language: Language
    content: str
    docstring: str = ""
    signature: str = ""
    start_line: int = 0
    end_line: int = 0
    file_path: str = ""
    parent_id: str = ""
    children: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    embedding: Optional[list[float]] = None
    metadata: dict = field(default_factory=dict)

    @property
    def qualified_name(self) -> str:
        """Get fully qualified name."""
        parts = [self.file_path] if self.file_path else []
        if self.parent_id:
            parts.append(
                self.parent_id.split("_")[-1]
                if "_" in self.parent_id
                else self.parent_id
            )
        parts.append(self.name)
        return "::".join(parts)

    @property
    def source_location(self) -> str:
        """Get source location string."""
        return f"{self.file_path}:{self.start_line}-{self.end_line}"


@dataclass
class CodeFile:
    """A source code file."""

    path: str
    language: Language
    content: str
    elements: list[CodeElement] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def line_count(self) -> int:
        return self.content.count("\n") + 1


@dataclass
class CodeSearchResult:
    """Result from code search."""

    element: CodeElement
    score: float
    rank: int
    match_type: str
    context: str = ""  # Surrounding code context
    explanation: str = ""


@dataclass
class DependencyGraph:
    """Dependency graph for the codebase."""

    nodes: dict[str, CodeElement] = field(default_factory=dict)
    edges: list[tuple[str, str, str]] = field(default_factory=list)  # (from, to, type)

    def add_dependency(self, from_id: str, to_id: str, dep_type: str = "imports"):
        """Add a dependency edge."""
        self.edges.append((from_id, to_id, dep_type))

    def get_dependencies(self, element_id: str) -> list[str]:
        """Get what an element depends on."""
        return [to_id for from_id, to_id, _ in self.edges if from_id == element_id]

    def get_dependents(self, element_id: str) -> list[str]:
        """Get what depends on an element."""
        return [from_id for from_id, to_id, _ in self.edges if to_id == element_id]


# ══════════════════════════════════════════════════════════════════════════════
# CODE PARSERS
# ══════════════════════════════════════════════════════════════════════════════


class CodeParser(ABC):
    """Abstract base class for language-specific parsers."""

    @abstractmethod
    def parse(self, content: str, file_path: str) -> list[CodeElement]:
        """Parse code content and extract elements."""
        pass

    @abstractmethod
    def get_imports(self, content: str) -> list[str]:
        """Extract import statements."""
        pass


class PythonParser(CodeParser):
    """Parser for Python code."""

    def parse(self, content: str, file_path: str) -> list[CodeElement]:
        """Parse Python code using regex-based extraction."""
        elements = []
        lines = content.split("\n")

        # Find classes
        class_pattern = r"^class\s+(\w+)(?:\([^)]*\))?:"
        func_pattern = r"^(\s*)def\s+(\w+)\s*\([^)]*\)(?:\s*->\s*[^:]+)?:"

        current_class = None
        current_class_indent = 0

        for i, line in enumerate(lines):
            # Check for class
            class_match = re.match(class_pattern, line)
            if class_match:
                class_name = class_match.group(1)
                class_content, end_line = self._extract_block(lines, i)
                docstring = self._extract_docstring(lines, i + 1)

                element = CodeElement(
                    id=f"{file_path}::class::{class_name}",
                    name=class_name,
                    element_type=CodeElementType.CLASS,
                    language=Language.PYTHON,
                    content=class_content,
                    docstring=docstring,
                    signature=line.strip(),
                    start_line=i + 1,
                    end_line=end_line + 1,
                    file_path=file_path,
                )
                elements.append(element)
                current_class = element
                current_class_indent = 0
                continue

            # Check for function/method
            func_match = re.match(func_pattern, line)
            if func_match:
                indent = len(func_match.group(1))
                func_name = func_match.group(2)

                if func_name.startswith("_") and not func_name.startswith("__"):
                    visibility = "private"
                elif func_name.startswith("__") and func_name.endswith("__"):
                    visibility = "dunder"
                else:
                    visibility = "public"

                func_content, end_line = self._extract_block(lines, i)
                docstring = self._extract_docstring(lines, i + 1)

                # Determine if method or function
                is_method = current_class and indent > current_class_indent

                element = CodeElement(
                    id=f"{file_path}::{'method' if is_method else 'func'}::{func_name}",
                    name=func_name,
                    element_type=(
                        CodeElementType.METHOD
                        if is_method
                        else CodeElementType.FUNCTION
                    ),
                    language=Language.PYTHON,
                    content=func_content,
                    docstring=docstring,
                    signature=line.strip(),
                    start_line=i + 1,
                    end_line=end_line + 1,
                    file_path=file_path,
                    parent_id=current_class.id if is_method else "",
                    metadata={"visibility": visibility},
                )

                if is_method:
                    current_class.children.append(element.id)

                elements.append(element)

        return elements

    def _extract_block(self, lines: list[str], start_idx: int) -> tuple[str, int]:
        """Extract a code block starting at given index."""
        if start_idx >= len(lines):
            return "", start_idx

        # Get base indentation
        first_line = lines[start_idx]
        base_indent = len(first_line) - len(first_line.lstrip())

        block_lines = [first_line]
        end_idx = start_idx

        for i in range(start_idx + 1, len(lines)):
            line = lines[i]

            # Empty line - include but don't end block
            if not line.strip():
                block_lines.append(line)
                end_idx = i
                continue

            # Get current indentation
            current_indent = len(line) - len(line.lstrip())

            # If we hit a line at same or less indentation (and not blank), stop
            if current_indent <= base_indent and line.strip():
                # But check if it's a decorator for another def
                if not line.strip().startswith("@"):
                    break

            block_lines.append(line)
            end_idx = i

        return "\n".join(block_lines), end_idx

    def _extract_docstring(self, lines: list[str], start_idx: int) -> str:
        """Extract docstring if present."""
        if start_idx >= len(lines):
            return ""

        # Skip to first non-empty line
        while start_idx < len(lines) and not lines[start_idx].strip():
            start_idx += 1

        if start_idx >= len(lines):
            return ""

        line = lines[start_idx].strip()

        # Check for docstring
        for quote in ['"""', "'''"]:
            if line.startswith(quote):
                # Single line docstring
                if line.count(quote) >= 2:
                    return line.strip(quote).strip()

                # Multi-line docstring
                docstring_lines = [line[3:]]
                for i in range(start_idx + 1, len(lines)):
                    if quote in lines[i]:
                        docstring_lines.append(lines[i].split(quote)[0])
                        break
                    docstring_lines.append(lines[i].strip())

                return "\n".join(docstring_lines).strip()

        return ""

    def get_imports(self, content: str) -> list[str]:
        """Extract Python imports."""
        imports = []

        # Standard imports
        for match in re.finditer(r"^import\s+(\S+)", content, re.MULTILINE):
            imports.append(match.group(1))

        # From imports
        for match in re.finditer(r"^from\s+(\S+)\s+import", content, re.MULTILINE):
            imports.append(match.group(1))

        return imports


class JavaScriptParser(CodeParser):
    """Parser for JavaScript/TypeScript code."""

    def parse(self, content: str, file_path: str) -> list[CodeElement]:
        """Parse JavaScript/TypeScript code."""
        elements = []
        lines = content.split("\n")

        # Detect language
        is_ts = file_path.endswith((".ts", ".tsx"))
        lang = Language.TYPESCRIPT if is_ts else Language.JAVASCRIPT

        # Function patterns
        patterns = [
            # Arrow functions: const name = (...) =>
            r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*(?::\s*[^=]+)?\s*=>",
            # Regular functions: function name(...)
            r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)",
            # Class methods: name(...) {
            r"^\s+(?:async\s+)?(\w+)\s*\([^)]*\)\s*(?::\s*[^{]+)?\s*{",
        ]

        # Class pattern
        class_pattern = r"(?:export\s+)?class\s+(\w+)(?:\s+extends\s+\w+)?(?:\s+implements\s+[\w,\s]+)?\s*{"

        # Interface pattern (TypeScript)
        interface_pattern = (
            r"(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+[\w,\s]+)?\s*{"
        )

        for i, line in enumerate(lines):
            # Check for class
            class_match = re.search(class_pattern, line)
            if class_match:
                class_name = class_match.group(1)
                class_content, end_line = self._extract_brace_block(lines, i)

                element = CodeElement(
                    id=f"{file_path}::class::{class_name}",
                    name=class_name,
                    element_type=CodeElementType.CLASS,
                    language=lang,
                    content=class_content,
                    signature=line.strip(),
                    start_line=i + 1,
                    end_line=end_line + 1,
                    file_path=file_path,
                )
                elements.append(element)
                continue

            # Check for interface (TypeScript)
            if is_ts:
                interface_match = re.search(interface_pattern, line)
                if interface_match:
                    interface_name = interface_match.group(1)
                    interface_content, end_line = self._extract_brace_block(lines, i)

                    element = CodeElement(
                        id=f"{file_path}::interface::{interface_name}",
                        name=interface_name,
                        element_type=CodeElementType.INTERFACE,
                        language=lang,
                        content=interface_content,
                        signature=line.strip(),
                        start_line=i + 1,
                        end_line=end_line + 1,
                        file_path=file_path,
                    )
                    elements.append(element)
                    continue

            # Check for functions
            for pattern in patterns:
                func_match = re.search(pattern, line)
                if func_match:
                    func_name = func_match.group(1)

                    # Skip common non-function names
                    if func_name in {"if", "for", "while", "switch", "catch"}:
                        continue

                    func_content, end_line = self._extract_brace_block(lines, i)
                    jsdoc = self._extract_jsdoc(lines, i)

                    element = CodeElement(
                        id=f"{file_path}::func::{func_name}",
                        name=func_name,
                        element_type=CodeElementType.FUNCTION,
                        language=lang,
                        content=func_content,
                        docstring=jsdoc,
                        signature=line.strip(),
                        start_line=i + 1,
                        end_line=end_line + 1,
                        file_path=file_path,
                    )
                    elements.append(element)
                    break

        return elements

    def _extract_brace_block(self, lines: list[str], start_idx: int) -> tuple[str, int]:
        """Extract a brace-delimited block."""
        if start_idx >= len(lines):
            return "", start_idx

        block_lines = []
        brace_count = 0
        started = False
        end_idx = start_idx

        for i in range(start_idx, len(lines)):
            line = lines[i]
            block_lines.append(line)
            end_idx = i

            # Count braces (simple, doesn't handle strings/comments)
            brace_count += line.count("{") - line.count("}")

            if "{" in line:
                started = True

            if started and brace_count <= 0:
                break

        return "\n".join(block_lines), end_idx

    def _extract_jsdoc(self, lines: list[str], func_idx: int) -> str:
        """Extract JSDoc comment before function."""
        if func_idx == 0:
            return ""

        # Look backwards for JSDoc
        end_idx = func_idx - 1

        # Skip empty lines
        while end_idx >= 0 and not lines[end_idx].strip():
            end_idx -= 1

        if end_idx < 0:
            return ""

        # Check if it ends with */
        if not lines[end_idx].strip().endswith("*/"):
            return ""

        # Find start of JSDoc
        start_idx = end_idx
        while start_idx >= 0:
            if "/**" in lines[start_idx]:
                break
            start_idx -= 1

        if start_idx < 0:
            return ""

        # Extract and clean JSDoc
        jsdoc_lines = []
        for i in range(start_idx, end_idx + 1):
            line = lines[i].strip()
            line = re.sub(r"^/\*\*\s*", "", line)
            line = re.sub(r"\s*\*/$", "", line)
            line = re.sub(r"^\*\s*", "", line)
            if line:
                jsdoc_lines.append(line)

        return "\n".join(jsdoc_lines)

    def get_imports(self, content: str) -> list[str]:
        """Extract JavaScript/TypeScript imports."""
        imports = []

        # ES6 imports
        for match in re.finditer(r"import\s+.*\s+from\s+['\"]([^'\"]+)['\"]", content):
            imports.append(match.group(1))

        # CommonJS requires
        for match in re.finditer(r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", content):
            imports.append(match.group(1))

        return imports


class JavaParser(CodeParser):
    """Parser for Java code."""

    def parse(self, content: str, file_path: str) -> list[CodeElement]:
        """Parse Java code."""
        elements = []
        lines = content.split("\n")

        # Class/interface pattern
        class_pattern = r"(?:public\s+|private\s+|protected\s+)?(?:abstract\s+|final\s+)?(?:class|interface|enum)\s+(\w+)"

        # Method pattern
        method_pattern = r"^\s*(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:final\s+)?(?:abstract\s+)?(?:<[^>]+>\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*\([^)]*\)"

        current_class = None

        for i, line in enumerate(lines):
            # Check for class/interface
            class_match = re.search(class_pattern, line)
            if class_match:
                class_name = class_match.group(1)
                class_content, end_line = self._extract_brace_block(lines, i)
                javadoc = self._extract_javadoc(lines, i)

                # Determine type
                if "interface " in line:
                    elem_type = CodeElementType.INTERFACE
                elif "enum " in line:
                    elem_type = CodeElementType.ENUM
                else:
                    elem_type = CodeElementType.CLASS

                element = CodeElement(
                    id=f"{file_path}::class::{class_name}",
                    name=class_name,
                    element_type=elem_type,
                    language=Language.JAVA,
                    content=class_content,
                    docstring=javadoc,
                    signature=line.strip(),
                    start_line=i + 1,
                    end_line=end_line + 1,
                    file_path=file_path,
                )
                elements.append(element)
                current_class = element
                continue

            # Check for method
            method_match = re.search(method_pattern, line)
            if method_match and current_class:
                return_type = method_match.group(1)
                method_name = method_match.group(2)

                # Skip constructors (name == class name)
                if method_name == current_class.name:
                    continue

                method_content, end_line = self._extract_brace_block(lines, i)
                javadoc = self._extract_javadoc(lines, i)

                element = CodeElement(
                    id=f"{file_path}::method::{method_name}",
                    name=method_name,
                    element_type=CodeElementType.METHOD,
                    language=Language.JAVA,
                    content=method_content,
                    docstring=javadoc,
                    signature=line.strip(),
                    start_line=i + 1,
                    end_line=end_line + 1,
                    file_path=file_path,
                    parent_id=current_class.id,
                    metadata={"return_type": return_type},
                )
                current_class.children.append(element.id)
                elements.append(element)

        return elements

    def _extract_brace_block(self, lines: list[str], start_idx: int) -> tuple[str, int]:
        """Extract a brace-delimited block."""
        block_lines = []
        brace_count = 0
        started = False
        end_idx = start_idx

        for i in range(start_idx, len(lines)):
            line = lines[i]
            block_lines.append(line)
            end_idx = i

            brace_count += line.count("{") - line.count("}")

            if "{" in line:
                started = True

            if started and brace_count <= 0:
                break

        return "\n".join(block_lines), end_idx

    def _extract_javadoc(self, lines: list[str], func_idx: int) -> str:
        """Extract Javadoc comment."""
        if func_idx == 0:
            return ""

        end_idx = func_idx - 1

        # Skip empty lines and annotations
        while end_idx >= 0:
            stripped = lines[end_idx].strip()
            if not stripped or stripped.startswith("@"):
                end_idx -= 1
            else:
                break

        if end_idx < 0 or not lines[end_idx].strip().endswith("*/"):
            return ""

        # Find start
        start_idx = end_idx
        while start_idx >= 0:
            if "/**" in lines[start_idx]:
                break
            start_idx -= 1

        if start_idx < 0:
            return ""

        # Extract
        doc_lines = []
        for i in range(start_idx, end_idx + 1):
            line = lines[i].strip()
            line = re.sub(r"^/\*\*\s*", "", line)
            line = re.sub(r"\s*\*/$", "", line)
            line = re.sub(r"^\*\s*", "", line)
            if line:
                doc_lines.append(line)

        return "\n".join(doc_lines)

    def get_imports(self, content: str) -> list[str]:
        """Extract Java imports."""
        imports = []
        for match in re.finditer(r"^import\s+([\w.]+);", content, re.MULTILINE):
            imports.append(match.group(1))
        return imports


class CodeParserFactory:
    """Factory for creating language-specific parsers."""

    _parsers: dict[Language, CodeParser] = {
        Language.PYTHON: PythonParser(),
        Language.JAVASCRIPT: JavaScriptParser(),
        Language.TYPESCRIPT: JavaScriptParser(),
        Language.JAVA: JavaParser(),
    }

    _extension_map: dict[str, Language] = {
        ".py": Language.PYTHON,
        ".js": Language.JAVASCRIPT,
        ".jsx": Language.JAVASCRIPT,
        ".ts": Language.TYPESCRIPT,
        ".tsx": Language.TYPESCRIPT,
        ".java": Language.JAVA,
        ".go": Language.GO,
        ".rs": Language.RUST,
        ".cpp": Language.CPP,
        ".hpp": Language.CPP,
        ".c": Language.CPP,
        ".h": Language.CPP,
        ".cs": Language.CSHARP,
    }

    @classmethod
    def get_parser(cls, language: Language) -> Optional[CodeParser]:
        """Get parser for a language."""
        return cls._parsers.get(language)

    @classmethod
    def detect_language(cls, file_path: str) -> Language:
        """Detect language from file extension."""
        ext = Path(file_path).suffix.lower()
        return cls._extension_map.get(ext, Language.UNKNOWN)


# ══════════════════════════════════════════════════════════════════════════════
# EMBEDDING AND SEARCH
# ══════════════════════════════════════════════════════════════════════════════


class CodeEmbedder:
    """Generate embeddings for code elements."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self._dimension = 384

    def _load_model(self):
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self.model = SentenceTransformer(self.model_name)
                self._dimension = self.model.get_sentence_embedding_dimension()
            except ImportError:
                self.model = "mock"

    def embed_element(self, element: CodeElement) -> list[float]:
        """Generate embedding for a code element."""
        # Create rich text representation for embedding
        text_parts = [
            f"{element.element_type.value}: {element.name}",
            element.docstring or "",
            element.signature,
            element.content[:500] if len(element.content) > 500 else element.content,
        ]

        text = "\n".join(filter(None, text_parts))
        return self.embed(text)

    def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        self._load_model()

        if self.model == "mock":
            return self._mock_embedding(text)

        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        self._load_model()

        if self.model == "mock":
            return [self._mock_embedding(t) for t in texts]

        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    def _mock_embedding(self, text: str) -> list[float]:
        """Generate deterministic mock embedding."""
        hash_val = hashlib.md5(text.encode()).hexdigest()

        embedding = []
        for i in range(0, min(len(hash_val), self._dimension), 2):
            val = int(hash_val[i : i + 2], 16) / 255.0 - 0.5
            embedding.append(val)

        while len(embedding) < self._dimension:
            embedding.append(0.0)

        # Normalize
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding[: self._dimension]

    @property
    def dimension(self) -> int:
        return self._dimension


class CodeVectorStore:
    """Vector store for code elements."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.vectors: list[list[float]] = []
        self.element_ids: list[str] = []

    def add(self, element_id: str, vector: list[float]):
        """Add a code element vector."""
        self.element_ids.append(element_id)
        self.vectors.append(vector)

    def search(
        self, query_vector: list[float], top_k: int = 10
    ) -> list[tuple[str, float]]:
        """Search for similar code elements."""
        if not self.vectors:
            return []

        similarities = []
        for i, vec in enumerate(self.vectors):
            sim = self._cosine_similarity(query_vector, vec)
            similarities.append((self.element_ids[i], sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity."""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)


class CodeKeywordIndex:
    """Keyword index for exact code matching."""

    def __init__(self):
        self.elements: dict[str, CodeElement] = {}
        self.name_index: dict[str, list[str]] = {}  # name -> [element_ids]
        self.signature_index: dict[str, list[str]] = {}

    def add(self, element: CodeElement):
        """Add element to index."""
        self.elements[element.id] = element

        # Index by name
        name_lower = element.name.lower()
        if name_lower not in self.name_index:
            self.name_index[name_lower] = []
        self.name_index[name_lower].append(element.id)

        # Index signature words
        sig_words = re.findall(r"\b\w+\b", element.signature.lower())
        for word in sig_words:
            if len(word) > 2:
                if word not in self.signature_index:
                    self.signature_index[word] = []
                self.signature_index[word].append(element.id)

    def search_exact(self, name: str) -> list[str]:
        """Exact name match."""
        return self.name_index.get(name.lower(), [])

    def search_fuzzy(self, query: str) -> list[tuple[str, float]]:
        """Fuzzy keyword search."""
        query_words = set(re.findall(r"\b\w+\b", query.lower()))

        scores: dict[str, float] = {}

        for word in query_words:
            if len(word) <= 2:
                continue

            # Exact name match
            if word in self.name_index:
                for elem_id in self.name_index[word]:
                    scores[elem_id] = scores.get(elem_id, 0) + 2.0

            # Signature match
            if word in self.signature_index:
                for elem_id in self.signature_index[word]:
                    scores[elem_id] = scores.get(elem_id, 0) + 1.0

            # Partial name match
            for name, elem_ids in self.name_index.items():
                if word in name or name in word:
                    for elem_id in elem_ids:
                        scores[elem_id] = scores.get(elem_id, 0) + 0.5

        results = [(k, v) for k, v in scores.items()]
        results.sort(key=lambda x: x[1], reverse=True)
        return results


# ══════════════════════════════════════════════════════════════════════════════
# CODE RAG PIPELINE
# ══════════════════════════════════════════════════════════════════════════════


class CodeRAGPipeline:
    """Complete RAG pipeline for codebase analysis."""

    def __init__(self, config: CodeRAGConfig = None):
        self.config = config or CodeRAGConfig()

        # Components
        self.embedder = CodeEmbedder(self.config.embedding_model)
        self.vector_store = CodeVectorStore(self.config.embedding_dimension)
        self.keyword_index = CodeKeywordIndex()
        self.dependency_graph = DependencyGraph()

        # Storage
        self.files: dict[str, CodeFile] = {}
        self.elements: dict[str, CodeElement] = {}

    def add_file(self, path: str, content: str = None) -> CodeFile:
        """Add a source file to the index."""
        # Read file if content not provided
        if content is None:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

        # Detect language
        language = CodeParserFactory.detect_language(path)
        if language == Language.UNKNOWN:
            print(f"⚠️ Unsupported language: {path}")
            return None

        # Get parser
        parser = CodeParserFactory.get_parser(language)
        if not parser:
            print(f"⚠️ No parser for: {language}")
            return None

        # Parse file
        elements = parser.parse(content, path)
        imports = parser.get_imports(content)

        # Create file object
        code_file = CodeFile(
            path=path,
            language=language,
            content=content,
            elements=elements,
            imports=imports,
        )

        # Index elements
        for element in elements:
            self.elements[element.id] = element

            # Generate embedding
            element.embedding = self.embedder.embed_element(element)

            # Add to stores
            self.vector_store.add(element.id, element.embedding)
            self.keyword_index.add(element)
            self.dependency_graph.nodes[element.id] = element

        # Build dependency edges
        for imp in imports:
            for elem_id, elem in self.elements.items():
                if imp in elem.file_path or imp.endswith(elem.name):
                    for file_elem in elements:
                        self.dependency_graph.add_dependency(
                            file_elem.id, elem_id, "imports"
                        )

        self.files[path] = code_file
        return code_file

    def add_directory(
        self, directory: str, exclude_patterns: list[str] = None
    ) -> list[CodeFile]:
        """Add all code files from a directory."""
        exclude_patterns = exclude_patterns or [
            "__pycache__",
            "node_modules",
            ".git",
            ".venv",
            "venv",
            "build",
            "dist",
            ".idea",
            ".vscode",
        ]

        files = []
        root_path = Path(directory)

        for ext in [".py", ".js", ".jsx", ".ts", ".tsx", ".java"]:
            for file_path in root_path.rglob(f"*{ext}"):
                # Check exclusions
                skip = False
                for pattern in exclude_patterns:
                    if pattern in str(file_path):
                        skip = True
                        break

                if skip:
                    continue

                try:
                    code_file = self.add_file(str(file_path))
                    if code_file:
                        files.append(code_file)
                except Exception as e:
                    print(f"⚠️ Error parsing {file_path}: {e}")

        return files

    def search(
        self,
        query: str,
        top_k: int = None,
        element_types: list[CodeElementType] = None,
        languages: list[Language] = None,
    ) -> list[CodeSearchResult]:
        """Search for code elements by natural language description."""
        top_k = top_k or self.config.top_k

        # Semantic search
        query_embedding = self.embedder.embed(query)
        semantic_results = self.vector_store.search(query_embedding, top_k * 2)

        # Keyword search
        keyword_results = self.keyword_index.search_fuzzy(query)

        # Merge results
        element_scores: dict[str, tuple[float, str]] = {}

        # Normalize semantic scores
        if semantic_results:
            max_sem = max(r[1] for r in semantic_results)
            for elem_id, score in semantic_results:
                normalized = score / max_sem if max_sem > 0 else 0
                element_scores[elem_id] = (normalized * 0.6, "semantic")

        # Add keyword scores
        if keyword_results:
            max_kw = max(r[1] for r in keyword_results) if keyword_results else 1
            for elem_id, score in keyword_results[: top_k * 2]:
                normalized = score / max_kw if max_kw > 0 else 0
                weighted = normalized * 0.4

                if elem_id in element_scores:
                    old_score, _ = element_scores[elem_id]
                    element_scores[elem_id] = (old_score + weighted, "hybrid")
                else:
                    element_scores[elem_id] = (weighted, "keyword")

        # Sort and filter
        sorted_elements = sorted(
            element_scores.items(), key=lambda x: x[1][0], reverse=True
        )

        # Build results
        results = []
        for rank, (elem_id, (score, match_type)) in enumerate(
            sorted_elements[:top_k], 1
        ):
            if elem_id not in self.elements:
                continue

            element = self.elements[elem_id]

            # Filter by type
            if element_types and element.element_type not in element_types:
                continue

            # Filter by language
            if languages and element.language not in languages:
                continue

            results.append(
                CodeSearchResult(
                    element=element,
                    score=score,
                    rank=rank,
                    match_type=match_type,
                    context=self._get_context(element),
                    explanation=self._generate_explanation(element, query),
                )
            )

        return results[:top_k]

    def _get_context(self, element: CodeElement) -> str:
        """Get surrounding context for an element."""
        # Get parent if method
        context_parts = []

        if element.parent_id and element.parent_id in self.elements:
            parent = self.elements[element.parent_id]
            context_parts.append(f"In {parent.element_type.value} {parent.name}")

        # Get file info
        if element.file_path:
            context_parts.append(f"File: {element.file_path}")

        # Get dependencies
        deps = self.dependency_graph.get_dependencies(element.id)
        if deps:
            dep_names = [self.elements[d].name for d in deps if d in self.elements]
            if dep_names:
                context_parts.append(f"Uses: {', '.join(dep_names[:3])}")

        return " | ".join(context_parts)

    def _generate_explanation(self, element: CodeElement, query: str) -> str:
        """Generate explanation of why element matches query."""
        # Simple match explanation
        query_words = set(re.findall(r"\b\w+\b", query.lower()))
        element_words = set(
            re.findall(
                r"\b\w+\b",
                f"{element.name} {element.docstring} {element.signature}".lower(),
            )
        )

        matches = query_words & element_words

        if matches:
            return f"Matches: {', '.join(list(matches)[:5])}"

        return f"{element.element_type.value.title()} related to query"

    def find_function(self, name: str) -> Optional[CodeElement]:
        """Find function by exact name."""
        for elem_id, elem in self.elements.items():
            if elem.name.lower() == name.lower():
                if elem.element_type in [
                    CodeElementType.FUNCTION,
                    CodeElementType.METHOD,
                ]:
                    return elem
        return None

    def find_class(self, name: str) -> Optional[CodeElement]:
        """Find class by exact name."""
        for elem_id, elem in self.elements.items():
            if elem.name.lower() == name.lower():
                if elem.element_type == CodeElementType.CLASS:
                    return elem
        return None

    def get_dependencies(self, element_id: str) -> list[CodeElement]:
        """Get dependencies for an element."""
        dep_ids = self.dependency_graph.get_dependencies(element_id)
        return [self.elements[d] for d in dep_ids if d in self.elements]

    def get_dependents(self, element_id: str) -> list[CodeElement]:
        """Get elements that depend on this one."""
        dep_ids = self.dependency_graph.get_dependents(element_id)
        return [self.elements[d] for d in dep_ids if d in self.elements]

    def generate_documentation(self, element_id: str) -> str:
        """Generate documentation for a code element."""
        if element_id not in self.elements:
            return "Element not found"

        element = self.elements[element_id]

        doc_parts = [
            f"# {element.name}",
            "",
            f"**Type:** {element.element_type.value}",
            f"**Language:** {element.language.value}",
            f"**Location:** {element.source_location}",
        ]

        if element.docstring:
            doc_parts.extend(["", "## Description", element.docstring])

        doc_parts.extend(["", "## Signature", f"```\n{element.signature}\n```"])

        # Dependencies
        deps = self.get_dependencies(element_id)
        if deps:
            doc_parts.extend(["", "## Dependencies"])
            for dep in deps:
                doc_parts.append(f"- `{dep.name}` ({dep.element_type.value})")

        # Dependents
        dependents = self.get_dependents(element_id)
        if dependents:
            doc_parts.extend(["", "## Used By"])
            for dep in dependents:
                doc_parts.append(f"- `{dep.name}` ({dep.element_type.value})")

        # Source code
        doc_parts.extend(
            [
                "",
                "## Source Code",
                f"```{element.language.value}",
                element.content,
                "```",
            ]
        )

        return "\n".join(doc_parts)

    def get_stats(self) -> dict:
        """Get pipeline statistics."""
        type_counts = {}
        lang_counts = {}

        for elem in self.elements.values():
            type_counts[elem.element_type.value] = (
                type_counts.get(elem.element_type.value, 0) + 1
            )
            lang_counts[elem.language.value] = (
                lang_counts.get(elem.language.value, 0) + 1
            )

        return {
            "files": len(self.files),
            "elements": len(self.elements),
            "by_type": type_counts,
            "by_language": lang_counts,
            "dependency_edges": len(self.dependency_graph.edges),
        }


# ══════════════════════════════════════════════════════════════════════════════
# SAMPLE CODE FOR DEMO
# ══════════════════════════════════════════════════════════════════════════════

SAMPLE_PYTHON_CODE = '''
"""User authentication module."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import hashlib

@dataclass
class User:
    """Represents a user in the system."""
    id: str
    username: str
    email: str
    password_hash: str
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    
    def check_password(self, password: str) -> bool:
        """Verify if password matches the stored hash."""
        hashed = hashlib.sha256(password.encode()).hexdigest()
        return hashed == self.password_hash


class AuthService:
    """Service for handling user authentication."""
    
    def __init__(self, db_connection):
        """Initialize the auth service with a database connection."""
        self.db = db_connection
        self.active_sessions = {}
    
    def login(self, username: str, password: str) -> Optional[str]:
        """
        Authenticate user and create session.
        
        Args:
            username: The user's username
            password: The plaintext password
            
        Returns:
            Session token if successful, None otherwise
        """
        user = self.db.find_user(username)
        if user and user.check_password(password):
            token = self._generate_token()
            self.active_sessions[token] = user.id
            user.last_login = datetime.now()
            return token
        return None
    
    def logout(self, token: str) -> bool:
        """Invalidate a session token."""
        if token in self.active_sessions:
            del self.active_sessions[token]
            return True
        return False
    
    def verify_token(self, token: str) -> Optional[str]:
        """Verify token and return user ID if valid."""
        return self.active_sessions.get(token)
    
    def _generate_token(self) -> str:
        """Generate a secure session token."""
        import secrets
        return secrets.token_hex(32)


def hash_password(password: str) -> str:
    """Hash a password for storage."""
    return hashlib.sha256(password.encode()).hexdigest()


def validate_password_strength(password: str) -> tuple[bool, list[str]]:
    """
    Validate password meets security requirements.
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    if len(password) < 8:
        errors.append("Password must be at least 8 characters")
    
    if not any(c.isupper() for c in password):
        errors.append("Password must contain uppercase letter")
    
    if not any(c.islower() for c in password):
        errors.append("Password must contain lowercase letter")
    
    if not any(c.isdigit() for c in password):
        errors.append("Password must contain a digit")
    
    return len(errors) == 0, errors
'''

SAMPLE_JAVASCRIPT_CODE = """
/**
 * Shopping cart module
 */

/**
 * Represents a product in the catalog
 */
class Product {
  constructor(id, name, price, category) {
    this.id = id;
    this.name = name;
    this.price = price;
    this.category = category;
  }

  /**
   * Get formatted price string
   */
  getFormattedPrice() {
    return `$${this.price.toFixed(2)}`;
  }
}

/**
 * Shopping cart for managing user purchases
 */
class ShoppingCart {
  constructor(userId) {
    this.userId = userId;
    this.items = [];
    this.appliedCoupons = [];
  }

  /**
   * Add item to cart
   * @param {Product} product - Product to add
   * @param {number} quantity - Quantity to add
   */
  addItem(product, quantity = 1) {
    const existing = this.items.find(item => item.product.id === product.id);
    
    if (existing) {
      existing.quantity += quantity;
    } else {
      this.items.push({ product, quantity });
    }
  }

  /**
   * Remove item from cart
   * @param {string} productId - Product ID to remove
   */
  removeItem(productId) {
    this.items = this.items.filter(item => item.product.id !== productId);
  }

  /**
   * Calculate cart total
   * @returns {number} Total price
   */
  getTotal() {
    let total = this.items.reduce((sum, item) => {
      return sum + (item.product.price * item.quantity);
    }, 0);

    // Apply coupons
    for (const coupon of this.appliedCoupons) {
      total = total * (1 - coupon.discount);
    }

    return total;
  }

  /**
   * Apply a coupon code
   * @param {Object} coupon - Coupon to apply
   */
  applyCoupon(coupon) {
    if (!this.appliedCoupons.find(c => c.code === coupon.code)) {
      this.appliedCoupons.push(coupon);
    }
  }

  /**
   * Get cart item count
   */
  getItemCount() {
    return this.items.reduce((count, item) => count + item.quantity, 0);
  }
}

/**
 * Calculate shipping cost based on cart total
 * @param {number} cartTotal - Cart subtotal
 * @param {string} shippingMethod - Shipping method
 * @returns {number} Shipping cost
 */
function calculateShipping(cartTotal, shippingMethod) {
  if (cartTotal > 100) {
    return 0; // Free shipping over $100
  }

  const rates = {
    standard: 5.99,
    express: 12.99,
    overnight: 24.99
  };

  return rates[shippingMethod] || rates.standard;
}

export { Product, ShoppingCart, calculateShipping };
"""

SAMPLE_JAVA_CODE = """
package com.example.service;

import java.util.*;
import java.time.LocalDateTime;

/**
 * Service for managing orders in the e-commerce system.
 */
public class OrderService {
    
    private final OrderRepository orderRepository;
    private final InventoryService inventoryService;
    private final PaymentService paymentService;
    
    /**
     * Creates a new OrderService with required dependencies.
     *
     * @param orderRepository Repository for order persistence
     * @param inventoryService Service for inventory management
     * @param paymentService Service for payment processing
     */
    public OrderService(
            OrderRepository orderRepository,
            InventoryService inventoryService,
            PaymentService paymentService) {
        this.orderRepository = orderRepository;
        this.inventoryService = inventoryService;
        this.paymentService = paymentService;
    }
    
    /**
     * Creates a new order from the given cart.
     *
     * @param cart Shopping cart with items
     * @param customer Customer placing the order
     * @return Created order
     * @throws InsufficientStockException if items not available
     * @throws PaymentException if payment fails
     */
    public Order createOrder(Cart cart, Customer customer) {
        // Validate inventory
        for (CartItem item : cart.getItems()) {
            if (!inventoryService.checkStock(item.getProductId(), item.getQuantity())) {
                throw new InsufficientStockException(item.getProductId());
            }
        }
        
        // Calculate totals
        double subtotal = calculateSubtotal(cart);
        double tax = calculateTax(subtotal, customer.getAddress());
        double shipping = calculateShipping(cart, customer.getAddress());
        double total = subtotal + tax + shipping;
        
        // Process payment
        PaymentResult payment = paymentService.charge(
            customer.getPaymentMethod(),
            total
        );
        
        if (!payment.isSuccessful()) {
            throw new PaymentException(payment.getError());
        }
        
        // Create order
        Order order = new Order();
        order.setCustomerId(customer.getId());
        order.setItems(cart.getItems());
        order.setSubtotal(subtotal);
        order.setTax(tax);
        order.setShipping(shipping);
        order.setTotal(total);
        order.setPaymentId(payment.getTransactionId());
        order.setStatus(OrderStatus.CONFIRMED);
        order.setCreatedAt(LocalDateTime.now());
        
        // Reserve inventory
        for (CartItem item : cart.getItems()) {
            inventoryService.reserveStock(item.getProductId(), item.getQuantity());
        }
        
        // Save and return
        return orderRepository.save(order);
    }
    
    /**
     * Cancels an existing order.
     *
     * @param orderId ID of order to cancel
     * @return Updated order
     */
    public Order cancelOrder(String orderId) {
        Order order = orderRepository.findById(orderId)
            .orElseThrow(() -> new OrderNotFoundException(orderId));
        
        if (order.getStatus() == OrderStatus.SHIPPED) {
            throw new IllegalStateException("Cannot cancel shipped order");
        }
        
        // Refund payment
        paymentService.refund(order.getPaymentId());
        
        // Release inventory
        for (CartItem item : order.getItems()) {
            inventoryService.releaseStock(item.getProductId(), item.getQuantity());
        }
        
        order.setStatus(OrderStatus.CANCELLED);
        order.setCancelledAt(LocalDateTime.now());
        
        return orderRepository.save(order);
    }
    
    /**
     * Gets order status for a customer.
     *
     * @param orderId Order ID
     * @return Order status
     */
    public OrderStatus getOrderStatus(String orderId) {
        return orderRepository.findById(orderId)
            .map(Order::getStatus)
            .orElseThrow(() -> new OrderNotFoundException(orderId));
    }
    
    private double calculateSubtotal(Cart cart) {
        return cart.getItems().stream()
            .mapToDouble(item -> item.getPrice() * item.getQuantity())
            .sum();
    }
    
    private double calculateTax(double subtotal, Address address) {
        double taxRate = TaxService.getTaxRate(address.getState());
        return subtotal * taxRate;
    }
    
    private double calculateShipping(Cart cart, Address address) {
        int totalWeight = cart.getItems().stream()
            .mapToInt(item -> item.getWeight() * item.getQuantity())
            .sum();
        
        return ShippingCalculator.calculate(totalWeight, address);
    }
}
"""


# ══════════════════════════════════════════════════════════════════════════════
# MAIN DEMO
# ══════════════════════════════════════════════════════════════════════════════


def run_demo():
    """Run interactive code search demo."""
    print("=" * 70)
    print("🧠 Code Repository Assistant - RAG Demo")
    print("=" * 70)

    # Create pipeline
    config = CodeRAGConfig(top_k=5, rerank_top_k=3)
    pipeline = CodeRAGPipeline(config)

    # Load sample code
    print("\n📄 Loading sample codebase...")

    # Python auth module
    pipeline.add_file("auth/users.py", SAMPLE_PYTHON_CODE)
    print("  ✅ auth/users.py (Python)")

    # JavaScript shopping cart
    pipeline.add_file("cart/shopping.js", SAMPLE_JAVASCRIPT_CODE)
    print("  ✅ cart/shopping.js (JavaScript)")

    # Java order service
    pipeline.add_file("services/OrderService.java", SAMPLE_JAVA_CODE)
    print("  ✅ services/OrderService.java (Java)")

    # Show stats
    stats = pipeline.get_stats()
    print(f"\n📊 Codebase Stats:")
    print(f"   Files: {stats['files']}")
    print(f"   Elements: {stats['elements']}")
    print(f"   By type: {stats['by_type']}")
    print(f"   By language: {stats['by_language']}")

    # Sample queries
    sample_queries = [
        "How does user authentication work?",
        "Find the shopping cart total calculation",
        "Show me order cancellation logic",
        "Where is password validation?",
        "How are coupons applied?",
    ]

    print("\n" + "=" * 70)
    print("💡 Sample questions you can ask:")
    for q in sample_queries:
        print(f"   • {q}")

    # Interactive loop
    print("\n" + "=" * 70)
    print("💬 Search the codebase (type 'quit' to exit)")
    print("   Commands: 'doc <name>' - generate docs, 'stats' - show stats")
    print("=" * 70)

    while True:
        try:
            query = input("\n🔍 Search: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not query:
            continue

        if query.lower() == "quit":
            break

        if query.lower() == "stats":
            stats = pipeline.get_stats()
            print(f"\n📊 Pipeline Statistics:")
            for key, value in stats.items():
                print(f"   {key}: {value}")
            continue

        if query.lower().startswith("doc "):
            name = query[4:].strip()
            element = pipeline.find_function(name) or pipeline.find_class(name)
            if element:
                doc = pipeline.generate_documentation(element.id)
                print(f"\n{doc}")
            else:
                print(f"❌ Element '{name}' not found")
            continue

        # Search
        results = pipeline.search(query)

        if not results:
            print("\n❌ No results found")
            continue

        print(f"\n🔎 Found {len(results)} results:\n")

        for r in results:
            elem = r.element
            print(f"  {r.rank}. {elem.name} ({elem.element_type.value})")
            print(f"     Language: {elem.language.value}")
            print(f"     Location: {elem.source_location}")
            print(f"     Score: {r.score:.3f} ({r.match_type})")

            if elem.docstring:
                doc_preview = elem.docstring[:100]
                if len(elem.docstring) > 100:
                    doc_preview += "..."
                print(f"     Doc: {doc_preview}")

            print(f"     Context: {r.context}")
            print()

        # Show code for top result
        top = results[0]
        print(f"📝 Top result source ({top.element.name}):")
        print("-" * 50)
        code_preview = top.element.content[:400]
        if len(top.element.content) > 400:
            code_preview += "\n... (truncated)"
        print(code_preview)
        print("-" * 50)

    print("\n👋 Goodbye!")


def main():
    """Main entry point."""
    import sys

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return

    run_demo()


if __name__ == "__main__":
    main()
