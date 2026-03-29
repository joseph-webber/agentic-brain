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

"""Source code loaders for RAG pipelines.

Supports loading source code files with language detection and metadata extraction.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

# Language configurations
LANGUAGE_CONFIGS = {
    "python": {
        "extensions": {".py", ".pyw", ".pyi", ".pyx"},
        "mime_type": "text/x-python",
        "comment_single": "#",
        "comment_multi": ('"""', '"""'),
        "docstring_pattern": r'^"""[\s\S]*?"""',
    },
    "javascript": {
        "extensions": {".js", ".jsx", ".mjs", ".cjs"},
        "mime_type": "text/javascript",
        "comment_single": "//",
        "comment_multi": ("/*", "*/"),
    },
    "typescript": {
        "extensions": {".ts", ".tsx", ".mts", ".cts"},
        "mime_type": "text/typescript",
        "comment_single": "//",
        "comment_multi": ("/*", "*/"),
    },
    "java": {
        "extensions": {".java"},
        "mime_type": "text/x-java",
        "comment_single": "//",
        "comment_multi": ("/*", "*/"),
    },
    "kotlin": {
        "extensions": {".kt", ".kts"},
        "mime_type": "text/x-kotlin",
        "comment_single": "//",
        "comment_multi": ("/*", "*/"),
    },
    "go": {
        "extensions": {".go"},
        "mime_type": "text/x-go",
        "comment_single": "//",
        "comment_multi": ("/*", "*/"),
    },
    "rust": {
        "extensions": {".rs"},
        "mime_type": "text/x-rust",
        "comment_single": "//",
        "comment_multi": ("/*", "*/"),
    },
    "c": {
        "extensions": {".c", ".h"},
        "mime_type": "text/x-c",
        "comment_single": "//",
        "comment_multi": ("/*", "*/"),
    },
    "cpp": {
        "extensions": {".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"},
        "mime_type": "text/x-c++",
        "comment_single": "//",
        "comment_multi": ("/*", "*/"),
    },
    "csharp": {
        "extensions": {".cs"},
        "mime_type": "text/x-csharp",
        "comment_single": "//",
        "comment_multi": ("/*", "*/"),
    },
    "ruby": {
        "extensions": {".rb", ".rbw"},
        "mime_type": "text/x-ruby",
        "comment_single": "#",
        "comment_multi": ("=begin", "=end"),
    },
    "php": {
        "extensions": {".php", ".phtml", ".php5", ".php7"},
        "mime_type": "text/x-php",
        "comment_single": "//",
        "comment_multi": ("/*", "*/"),
    },
    "swift": {
        "extensions": {".swift"},
        "mime_type": "text/x-swift",
        "comment_single": "//",
        "comment_multi": ("/*", "*/"),
    },
    "scala": {
        "extensions": {".scala", ".sc"},
        "mime_type": "text/x-scala",
        "comment_single": "//",
        "comment_multi": ("/*", "*/"),
    },
    "shell": {
        "extensions": {".sh", ".bash", ".zsh", ".fish"},
        "mime_type": "text/x-shellscript",
        "comment_single": "#",
    },
    "sql": {
        "extensions": {".sql"},
        "mime_type": "text/x-sql",
        "comment_single": "--",
        "comment_multi": ("/*", "*/"),
    },
    "r": {
        "extensions": {".r", ".R"},
        "mime_type": "text/x-r",
        "comment_single": "#",
    },
    "lua": {
        "extensions": {".lua"},
        "mime_type": "text/x-lua",
        "comment_single": "--",
        "comment_multi": ("--[[", "]]"),
    },
    "perl": {
        "extensions": {".pl", ".pm"},
        "mime_type": "text/x-perl",
        "comment_single": "#",
        "comment_multi": ("=pod", "=cut"),
    },
    "haskell": {
        "extensions": {".hs", ".lhs"},
        "mime_type": "text/x-haskell",
        "comment_single": "--",
        "comment_multi": ("{-", "-}"),
    },
    "elixir": {
        "extensions": {".ex", ".exs"},
        "mime_type": "text/x-elixir",
        "comment_single": "#",
        "comment_multi": ('"""', '"""'),
    },
    "clojure": {
        "extensions": {".clj", ".cljs", ".cljc", ".edn"},
        "mime_type": "text/x-clojure",
        "comment_single": ";",
    },
}

# Build extension to language map
EXTENSION_TO_LANGUAGE = {}
for lang, config in LANGUAGE_CONFIGS.items():
    for ext in config["extensions"]:
        EXTENSION_TO_LANGUAGE[ext] = lang


class CodeLoader(BaseLoader):
    """Load source code files with language detection.

    Extracts code with metadata including language, line count,
    function/class detection, and comment extraction.

    Example:
        loader = CodeLoader(base_path="/projects/myapp")
        docs = loader.load_folder("src/")

        # Load specific languages only
        loader = CodeLoader(languages=["python", "typescript"])
        docs = loader.load_folder("src/")

        # Extract with comments stripped
        loader = CodeLoader(strip_comments=True)
        docs = loader.load_folder("lib/")
    """

    def __init__(
        self,
        base_path: Optional[str] = None,
        encoding: str = "utf-8",
        languages: Optional[list[str]] = None,
        strip_comments: bool = False,
        include_metadata: bool = True,
        max_file_size_mb: int = 10,
        max_line_length: int = 1000,
    ):
        """Initialize CodeLoader.

        Args:
            base_path: Base directory for relative paths
            encoding: File encoding (default: utf-8)
            languages: List of languages to include (None = all supported)
            strip_comments: Remove comments from code
            include_metadata: Extract code metadata (functions, classes, etc.)
            max_file_size_mb: Maximum file size to load
            max_line_length: Skip files with lines longer than this (binary detection)
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.encoding = encoding
        self.languages = set(languages) if languages else None
        self.strip_comments = strip_comments
        self.include_metadata = include_metadata
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self.max_line_length = max_line_length

        # Build supported extensions based on language filter
        self.supported_extensions: set[str] = set()
        if self.languages:
            for lang in self.languages:
                if lang in LANGUAGE_CONFIGS:
                    self.supported_extensions.update(
                        LANGUAGE_CONFIGS[lang]["extensions"]
                    )
        else:
            self.supported_extensions = set(EXTENSION_TO_LANGUAGE.keys())

    @property
    def source_name(self) -> str:
        return "local_code"

    def authenticate(self) -> bool:
        """No authentication needed for local files."""
        return True

    def _resolve_path(self, path: str) -> Path:
        """Resolve path relative to base_path."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.base_path / p

    def _detect_language(self, file_path: Path) -> Optional[str]:
        """Detect programming language from file extension."""
        return EXTENSION_TO_LANGUAGE.get(file_path.suffix.lower())

    def _is_text_file(self, content: str) -> bool:
        """Check if content appears to be text (not binary)."""
        # Check for null bytes (binary indicator)
        if "\x00" in content[:1024]:
            return False
        # Check for very long lines (likely minified or binary)
        for line in content.split("\n")[:50]:
            if len(line) > self.max_line_length:
                return False
        return True

    def _extract_python_metadata(self, content: str) -> dict:
        """Extract metadata from Python code."""
        metadata: dict[str, list[str]] = {"functions": [], "classes": [], "imports": []}

        # Find function definitions
        for match in re.finditer(
            r"^(?:async\s+)?def\s+(\w+)\s*\(", content, re.MULTILINE
        ):
            metadata["functions"].append(match.group(1))

        # Find class definitions
        for match in re.finditer(r"^class\s+(\w+)\s*[:\(]", content, re.MULTILINE):
            metadata["classes"].append(match.group(1))

        # Find imports
        for match in re.finditer(
            r"^(?:from\s+(\S+)\s+)?import\s+(.+)$", content, re.MULTILINE
        ):
            if match.group(1):
                metadata["imports"].append(
                    f"from {match.group(1)} import {match.group(2)}"
                )
            else:
                metadata["imports"].append(f"import {match.group(2)}")

        return metadata

    def _extract_js_metadata(self, content: str) -> dict:
        """Extract metadata from JavaScript/TypeScript code."""
        metadata: dict[str, list[str]] = {"functions": [], "classes": [], "imports": []}

        # Find function definitions
        patterns = [
            r"function\s+(\w+)\s*\(",  # function foo()
            r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[^=]+)\s*=>",  # arrow functions
            r"(\w+)\s*:\s*(?:async\s+)?function\s*\(",  # method in object
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, content):
                metadata["functions"].append(match.group(1))

        # Find class definitions
        for match in re.finditer(r"class\s+(\w+)", content):
            metadata["classes"].append(match.group(1))

        # Find imports
        for match in re.finditer(r"import\s+.+\s+from\s+['\"]([^'\"]+)['\"]", content):
            metadata["imports"].append(match.group(1))

        return metadata

    def _extract_metadata(self, content: str, language: str) -> dict:
        """Extract metadata based on language."""
        if not self.include_metadata:
            return {}

        if language == "python":
            return self._extract_python_metadata(content)
        elif language in ("javascript", "typescript"):
            return self._extract_js_metadata(content)

        # Generic metadata for other languages
        metadata = {"line_count": content.count("\n") + 1}
        return metadata

    def _strip_comments_from_code(self, content: str, language: str) -> str:
        """Remove comments from code."""
        if language not in LANGUAGE_CONFIGS:
            return content

        config = LANGUAGE_CONFIGS[language]

        # Remove single-line comments
        if "comment_single" in config:
            comment_single = str(config["comment_single"])
            pattern = rf"{re.escape(comment_single)}.*$"
            content = re.sub(pattern, "", content, flags=re.MULTILINE)

        # Remove multi-line comments
        if "comment_multi" in config:
            start, end = config["comment_multi"]  # type: ignore
            pattern = rf"{re.escape(str(start))}[\s\S]*?{re.escape(str(end))}"
            content = re.sub(pattern, "", content)

        return content

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a source code file by path."""
        file_path = self._resolve_path(doc_id)

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        if not file_path.is_file():
            logger.error(f"Not a file: {file_path}")
            return None

        # Check extension
        language = self._detect_language(file_path)
        if not language:
            logger.debug(f"Unsupported file type: {file_path.suffix}")
            return None

        # Check language filter
        if self.languages and language not in self.languages:
            logger.debug(f"Language {language} not in filter")
            return None

        file_size = file_path.stat().st_size
        if file_size > self.max_file_size:
            logger.warning(f"File too large: {file_path} ({file_size} bytes)")
            return None

        try:
            content = file_path.read_text(encoding=self.encoding)

            # Check if text file
            if not self._is_text_file(content):
                logger.debug(f"Binary or minified file skipped: {file_path}")
                return None

            # Get language config
            lang_config = LANGUAGE_CONFIGS[language]

            # Strip comments if requested
            if self.strip_comments:
                content = self._strip_comments_from_code(content, language)

            # Extract metadata
            code_metadata = self._extract_metadata(content, language)
            stat = file_path.stat()

            metadata = {
                "language": language,
                "extension": file_path.suffix,
                "encoding": self.encoding,
                "line_count": content.count("\n") + 1,
                **code_metadata,
            }

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=str(file_path.absolute()),
                filename=file_path.name,
                mime_type=str(lang_config["mime_type"]),
                created_at=datetime.fromtimestamp(stat.st_ctime),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                size_bytes=file_size,
                metadata=metadata,
            )
        except UnicodeDecodeError as e:
            logger.debug(f"Encoding error (likely binary): {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all source code files from a folder."""
        folder = self._resolve_path(folder_path)

        if not folder.exists():
            logger.error(f"Folder not found: {folder}")
            return []

        if not folder.is_dir():
            logger.error(f"Not a directory: {folder}")
            return []

        documents = []
        pattern = "**/*" if recursive else "*"

        for file_path in folder.glob(pattern):
            if (
                file_path.is_file()
                and file_path.suffix.lower() in self.supported_extensions
            ):
                doc = self.load_document(str(file_path))
                if doc:
                    documents.append(doc)

        logger.info(f"Loaded {len(documents)} code files from {folder}")
        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search for code files containing the query string."""
        results: list[LoadedDocument] = []
        query_lower = query.lower()

        for file_path in self.base_path.rglob("*"):
            if len(results) >= max_results:
                break

            if (
                file_path.is_file()
                and file_path.suffix.lower() in self.supported_extensions
            ):
                try:
                    # First check filename
                    if query_lower in file_path.name.lower():
                        doc = self.load_document(str(file_path))
                        if doc:
                            results.append(doc)
                            continue

                    # Then check content
                    content = file_path.read_text(encoding=self.encoding)
                    if query_lower in content.lower():
                        doc = self.load_document(str(file_path))
                        if doc:
                            results.append(doc)
                except Exception:
                    continue

        return results


class PythonLoader(CodeLoader):
    """Specialized loader for Python files.

    Example:
        loader = PythonLoader()
        docs = loader.load_folder("src/")
    """

    def __init__(self, **kwargs):
        kwargs["languages"] = ["python"]
        super().__init__(**kwargs)

    @property
    def source_name(self) -> str:
        return "local_python"


class JavaScriptLoader(CodeLoader):
    """Specialized loader for JavaScript files.

    Example:
        loader = JavaScriptLoader()
        docs = loader.load_folder("src/")
    """

    def __init__(self, **kwargs):
        kwargs["languages"] = ["javascript"]
        super().__init__(**kwargs)

    @property
    def source_name(self) -> str:
        return "local_javascript"


class TypeScriptLoader(CodeLoader):
    """Specialized loader for TypeScript files.

    Example:
        loader = TypeScriptLoader()
        docs = loader.load_folder("src/")
    """

    def __init__(self, **kwargs):
        kwargs["languages"] = ["typescript"]
        super().__init__(**kwargs)

    @property
    def source_name(self) -> str:
        return "local_typescript"


class JavaLoader(CodeLoader):
    """Specialized loader for Java files.

    Example:
        loader = JavaLoader()
        docs = loader.load_folder("src/main/java/")
    """

    def __init__(self, **kwargs):
        kwargs["languages"] = ["java"]
        super().__init__(**kwargs)

    @property
    def source_name(self) -> str:
        return "local_java"


__all__ = [
    "CodeLoader",
    "PythonLoader",
    "JavaScriptLoader",
    "TypeScriptLoader",
    "JavaLoader",
    "LANGUAGE_CONFIGS",
    "EXTENSION_TO_LANGUAGE",
]
