# SPDX-License-Identifier: Apache-2.0

r"""Rich Text Format processing utilities for agentic-brain.

This module focuses on providing reliable RTF ingestion and basic authoring
capabilities. While RTF is an older format, it is still encountered in many
enterprise workflows and messaging systems. The processor implemented here
combines the convenience of the ``striprtf`` library for plain-text extraction
with a custom parser that understands a curated subset of the RTF control
vocabulary. The parser targets the constructs most frequently encountered in
knowledge-worker documents, including:

* Paragraph demarcation (``\par`` and ``\pard``)
* Character formatting (bold, italic, underline, font size, font face, color)
* Unicode escapes (``\uNNNN``) with ASCII fallbacks
* Color and font tables
* Metadata blocks (``\info``)
* Embedded pictures stored as hexadecimal payloads

The processor emits structured ``DocumentContent`` objects that align with the
agentic-brain document model, making the results immediately useful for
downstream indexing, summarization, or transformation tasks. In addition, a
minimal ``RTFDocument`` helper is provided for generating simple RTF files with
headings and paragraphs so that automated agents can round-trip content in the
legacy format when needed.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

try:
    from striprtf.striprtf import rtf_to_text as _striprtf_to_text

    STRIPRTF_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    _striprtf_to_text = None
    STRIPRTF_AVAILABLE = False

from .models import (
    DocumentContent,
    DocumentStyle,
    Image,
    Metadata,
    OfficeFormat,
    Paragraph,
    TextRun,
)

logger = logging.getLogger(__name__)


def _fallback_rtf_to_text(raw: str) -> str:
    """Best-effort plain text extraction when ``striprtf`` is unavailable."""
    text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)
    text = re.sub(r"\\u-?\d+\??", " ", text)
    text = text.replace("\\par", "\n")
    text = text.replace("\\line", "\n")
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _rtf_to_text(raw: str) -> str:
    """Convert RTF to plain text with an optional dependency fallback."""
    if _striprtf_to_text is not None:
        return _striprtf_to_text(raw)
    return _fallback_rtf_to_text(raw)


# ---------------------------------------------------------------------------
# Helper data structures
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _TextState:
    """Represents the current character formatting state while parsing."""

    bold: bool = False
    italic: bool = False
    underline: bool = False
    font_size: float = 12.0  # points
    color_index: int = 0
    font_family: str = "Calibri"
    alignment: str = "left"

    def clone(self) -> _TextState:
        """Create a shallow copy for nested groups."""
        return _TextState(
            bold=self.bold,
            italic=self.italic,
            underline=self.underline,
            font_size=self.font_size,
            color_index=self.color_index,
            font_family=self.font_family,
            alignment=self.alignment,
        )

    def reset_character(self) -> None:
        """Reset inline character formatting to defaults."""
        self.bold = False
        self.italic = False
        self.underline = False
        self.font_size = 12.0
        self.color_index = 0
        self.font_family = "Calibri"

    def to_style(self, color_table: Dict[int, str]) -> DocumentStyle:
        """Convert the state into a ``DocumentStyle`` instance."""
        return DocumentStyle(
            font_family=self.font_family,
            font_size=self.font_size,
            bold=self.bold,
            italic=self.italic,
            underline=self.underline,
            text_color=color_table.get(self.color_index, "#000000"),
            alignment=self.alignment,
        )


@dataclass(slots=True)
class _RTFParagraphSpec:
    """Lightweight representation of a paragraph for writing."""

    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    heading_level: Optional[int] = None


class RTFDocument:
    """Helper for generating small RTF files with basic formatting."""

    def __init__(self, metadata: Optional[Metadata] = None):
        self.metadata = metadata or Metadata()
        self._paragraphs: List[_RTFParagraphSpec] = []

    # ------------------------------------------------------------------ #
    # Authoring helpers
    # ------------------------------------------------------------------ #

    def add_paragraph(
        self,
        text: str,
        *,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
    ) -> None:
        """Append a body paragraph. Formatting flags are optional."""
        self._paragraphs.append(
            _RTFParagraphSpec(
                text=text,
                bold=bold,
                italic=italic,
                underline=underline,
            )
        )

    def add_heading(self, text: str, level: int = 1) -> None:
        """Append a heading paragraph (levels are clamped to 1-6)."""
        level = max(1, min(6, level))
        self._paragraphs.append(
            _RTFParagraphSpec(
                text=text,
                bold=True,
                heading_level=level,
            )
        )

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #

    def _escape_text(self, text: str) -> str:
        """Escape control characters and emit UTF-16 where required."""
        escaped: List[str] = []
        for char in text:
            codepoint = ord(char)
            if char in {"\\", "{", "}"}:
                escaped.append(f"\\{char}")
            elif 32 <= codepoint <= 126:
                escaped.append(char)
            else:
                # Emit Unicode control word with ASCII placeholder '?'
                escaped.append(f"\\u{codepoint}?")
        return "".join(escaped)

    def _build_info_group(self) -> str:
        """Render metadata fields into the ``\\info`` destination."""
        parts: List[str] = ["{\\info"]
        if self.metadata.title:
            parts.append(f"{{\\title {self._escape_text(self.metadata.title)}}}")
        if self.metadata.author:
            parts.append(f"{{\\author {self._escape_text(self.metadata.author)}}}")
        if self.metadata.subject:
            parts.append(f"{{\\subject {self._escape_text(self.metadata.subject)}}}")
        if self.metadata.company:
            parts.append(f"{{\\company {self._escape_text(self.metadata.company)}}}")
        if self.metadata.category:
            parts.append(f"{{\\category {self._escape_text(self.metadata.category)}}}")
        if self.metadata.keywords:
            keyword_text = ", ".join(self.metadata.keywords)
            parts.append(f"{{\\keywords {self._escape_text(keyword_text)}}}")
        if self.metadata.custom_properties:
            for key, value in self.metadata.custom_properties.items():
                parts.append(
                    f"{{\\*\\docvar {self._escape_text(str(key))} "
                    f"{self._escape_text(str(value))}}}"
                )
        parts.append("}")
        return "".join(parts)

    def to_rtf(self) -> str:
        """Serialize the in-memory representation to raw RTF."""
        parts: List[str] = ["{\\rtf1\\ansi\\deff0"]
        info = self._build_info_group()
        if info != "{\\info}":
            parts.append(info)

        for paragraph in self._paragraphs:
            parts.append("\\pard\\sa200\\sl276\\slmult1 ")

            if paragraph.heading_level is not None:
                parts.append(f"\\outlinelevel{paragraph.heading_level} ")
                parts.append("\\b ")

            if paragraph.bold and paragraph.heading_level is None:
                parts.append("\\b ")
            if paragraph.italic:
                parts.append("\\i ")
            if paragraph.underline:
                parts.append("\\ul ")

            parts.append(self._escape_text(paragraph.text))
            parts.append("\\par\n")

            if paragraph.heading_level is not None or paragraph.bold:
                parts.append("\\b0 ")
            if paragraph.italic:
                parts.append("\\i0 ")
            if paragraph.underline:
                parts.append("\\ulnone ")

        parts.append("}")
        return "".join(parts)

    def save(self, path: str | Path) -> Path:
        """Persist the generated RTF file to disk."""
        target = Path(path)
        target.write_text(self.to_rtf(), encoding="utf-8")
        return target


# ---------------------------------------------------------------------------
# RTF Processor
# ---------------------------------------------------------------------------


class RTFProcessor:
    """Parser and writer utility for Rich Text Format documents."""

    def __init__(self) -> None:
        self._raw_bytes: Optional[bytes] = None
        self._raw_text: Optional[str] = None
        self._encoding: str = "utf-8"
        self._current_path: Optional[Path] = None
        self._paragraphs_cache: Optional[List[Paragraph]] = None
        self._metadata_cache: Optional[Metadata] = None
        self._images_cache: Optional[List[Image]] = None
        self._info_group: Optional[str] = None
        self._color_table: Dict[int, str] = {0: "#000000"}
        self._font_table: Dict[int, str] = {}

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def parse(self, path: str | Path) -> DocumentContent:
        """Parse an RTF document into a structured ``DocumentContent``."""
        self._load_data(Path(path))

        paragraphs = self.extract_paragraphs()
        metadata = self.extract_metadata()
        images = self._extract_images()

        document = DocumentContent(
            format=OfficeFormat.RTF,
            paragraphs=paragraphs,
            images=images,
            metadata=metadata,
        )
        properties: Dict[str, str | float | bool] = {
            "encoding": self._encoding,
            "paragraph_count": float(len(paragraphs)),
            "image_count": float(len(images)),
        }
        if self._current_path:
            properties["path"] = str(self._current_path)
        document.document_properties.update(properties)
        document.resources["raw_rtf"] = self._raw_bytes or b""
        document.resources["color_table.json"] = json.dumps(self._color_table).encode(
            "utf-8"
        )
        return document

    def extract_text(self, path: Optional[str | Path] = None) -> str:
        """
        Extract plain text using ``striprtf``. When ``path`` is omitted, the
        method relies on the most recently parsed document.
        """
        if path is not None:
            raw = Path(path).read_text(encoding="latin-1", errors="ignore")
            return _rtf_to_text(raw)

        self._ensure_data_loaded()
        assert self._raw_text is not None
        return _rtf_to_text(self._raw_text)

    def extract_paragraphs(self) -> List[Paragraph]:
        """Return document paragraphs with basic formatting metadata."""
        self._ensure_data_loaded()
        if self._paragraphs_cache is None:
            self._paragraphs_cache = self._parse_paragraphs(self._raw_text or "")
        return self._paragraphs_cache

    def extract_formatted_text(self) -> str:
        """Render a Markdown-like representation preserving emphasis."""
        formatted_lines: List[str] = []
        for paragraph in self.extract_paragraphs():
            segments: List[str] = []
            for run in paragraph.runs:
                text = run.text
                if run.style.bold:
                    text = f"**{text}**"
                if run.style.italic:
                    text = f"*{text}*"
                if run.style.underline:
                    text = f"__{text}__"
                segments.append(text)

            joined = "".join(segments).strip()
            if not joined:
                continue

            if paragraph.is_heading and paragraph.heading_level:
                prefix = "#" * max(1, min(6, paragraph.heading_level))
                formatted_lines.append(f"{prefix} {joined}")
            else:
                formatted_lines.append(joined)

        return "\n\n".join(formatted_lines)

    def extract_metadata(self) -> Metadata:
        """Parse the ``\\info`` group and return a ``Metadata`` instance."""
        self._ensure_data_loaded()
        if self._metadata_cache is not None:
            return self._metadata_cache

        metadata = Metadata()
        info_group = self._info_group or self._capture_group(
            self._raw_text or "", "info"
        )
        self._info_group = info_group

        def info_value(key: str) -> Optional[str]:
            block = self._capture_group(info_group or "", key)
            if not block:
                return None
            return _rtf_to_text(block).strip()

        metadata.title = info_value("title") or (
            self._current_path.stem if self._current_path else None
        )
        metadata.author = info_value("author")
        metadata.subject = info_value("subject")
        metadata.company = info_value("company")
        metadata.category = info_value("category")

        keywords = info_value("keywords")
        metadata.keywords = self._parse_keywords(keywords)

        metadata.created_at = self._parse_datetime_group(
            self._capture_group(info_group or "", "creatim")
        )
        metadata.modified_at = self._parse_datetime_group(
            self._capture_group(info_group or "", "revtim")
        )
        metadata.last_printed_at = self._parse_datetime_group(
            self._capture_group(info_group or "", "printim")
        )

        revision = info_value("version") or info_value("edmins")
        if revision:
            metadata.revision = revision.strip()

        comments = info_value("doccomm")
        if comments:
            metadata.custom_properties["comments"] = comments

        self._metadata_cache = metadata
        return metadata

    def extract_metadata_dict(self) -> Dict[str, str]:
        """Convenience for code paths that prefer plain dictionaries."""
        metadata = self.extract_metadata()
        result = {
            "title": metadata.title or "",
            "author": metadata.author or "",
            "subject": metadata.subject or "",
            "company": metadata.company or "",
            "category": metadata.category or "",
            "revision": metadata.revision or "",
        }
        if metadata.keywords:
            result["keywords"] = ", ".join(metadata.keywords)
        if metadata.created_at:
            result["created_at"] = metadata.created_at.isoformat()
        if metadata.modified_at:
            result["modified_at"] = metadata.modified_at.isoformat()
        if metadata.last_printed_at:
            result["last_printed_at"] = metadata.last_printed_at.isoformat()
        return result

    def detect_encoding(self, data: Optional[bytes] = None) -> str:
        """Best-effort encoding detection based on control words."""
        raw = data or self._raw_bytes
        if not raw:
            return "utf-8"

        header = raw[:2048].decode("latin-1", errors="ignore")
        match = re.search(r"\\ansicpg(\d+)", header)
        if match:
            return f"cp{match.group(1)}"

        if "\\mac" in header:
            return "mac_roman"
        if "\\pc" in header:
            return "cp437"
        if "\\pca" in header:
            return "cp850"
        if "\\unicode" in header:
            return "utf-16-le"

        return "utf-8"

    def create_document(self, metadata: Optional[Metadata] = None) -> RTFDocument:
        """Factory for creating writable ``RTFDocument`` instances."""
        return RTFDocument(metadata=metadata)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _load_data(self, path: Path) -> None:
        if not path.exists():
            raise FileNotFoundError(f"RTF file not found: {path}")
        self._current_path = path
        self._raw_bytes = path.read_bytes()
        self._encoding = self.detect_encoding(self._raw_bytes)

        try:
            self._raw_text = self._raw_bytes.decode(self._encoding, errors="ignore")
        except LookupError:
            logger.warning("Unknown encoding %s, falling back to UTF-8", self._encoding)
            self._encoding = "utf-8"
            self._raw_text = self._raw_bytes.decode(self._encoding, errors="ignore")

        self._reset_caches()
        self._color_table = self._extract_color_table(self._raw_text)
        self._font_table = self._extract_font_table(self._raw_text)
        self._info_group = self._capture_group(self._raw_text, "info")

    def _reset_caches(self) -> None:
        self._paragraphs_cache = None
        self._metadata_cache = None
        self._images_cache = None

    def _ensure_data_loaded(self) -> None:
        if self._raw_text is None:
            raise ValueError("No RTF document loaded. Call parse() first.")

    # ------------------------------------------------------------------ #
    # Parsing logic
    # ------------------------------------------------------------------ #

    def _parse_paragraphs(self, data: str) -> List[Paragraph]:
        state_stack: List[_TextState] = [self._default_state()]
        paragraphs: List[Paragraph] = []
        current_runs: List[TextRun] = []
        text_buffer: List[str] = []

        i = 0
        length = len(data)

        def flush_text() -> None:
            if not text_buffer:
                return
            state = state_stack[-1]
            text = "".join(text_buffer)
            text_buffer.clear()
            if not text:
                return
            current_runs.append(
                TextRun(text=text, style=state.to_style(self._color_table))
            )

        def finalize_paragraph() -> None:
            flush_text()
            if not current_runs:
                return
            style = self._build_paragraph_style(current_runs)
            heading_level = self._infer_heading_level(style)
            paragraphs.append(
                Paragraph(
                    runs=current_runs.copy(),
                    style=style,
                    is_heading=heading_level is not None,
                    heading_level=heading_level,
                )
            )
            current_runs.clear()

        while i < length:
            char = data[i]

            # Skip carriage returns
            if char in {"\n", "\r"}:
                i += 1
                continue

            # Destination groups we do not need to process for text.
            if char == "{" and self._matches(data, i, "{\\*"):
                i = self._skip_group(data, i)
                continue
            if char == "{" and (
                self._matches(data, i, "{\\fonttbl")
                or self._matches(data, i, "{\\colortbl")
                or self._matches(data, i, "{\\info")
                or self._matches(data, i, "{\\stylesheet")
            ):
                i = self._skip_group(data, i)
                continue
            if char == "{" and self._matches(data, i, "{\\pict"):
                # Images are handled separately; skip binary payload.
                i = self._skip_group(data, i)
                continue

            if char == "{":
                state_stack.append(state_stack[-1].clone())
                i += 1
                continue

            if char == "}":
                flush_text()
                if len(state_stack) > 1:
                    state_stack.pop()
                i += 1
                continue

            if char == "\\":
                i = self._handle_control_word(
                    data, i + 1, state_stack, text_buffer, finalize_paragraph
                )
                continue

            text_buffer.append(char)
            i += 1

        finalize_paragraph()
        return paragraphs

    def _handle_control_word(
        self,
        data: str,
        index: int,
        state_stack: List[_TextState],
        text_buffer: List[str],
        finalize_paragraph: Callable[[], None],
    ) -> int:
        """Parse and apply a control word starting at ``data[index - 1]``."""
        if index >= len(data):
            return index

        state = state_stack[-1]
        char = data[index]

        # Literal braces or backslashes (control symbols)
        if char in ("\\", "{", "}"):
            text_buffer.append(char)
            return index + 1

        # Hex-encoded characters: \'hh
        if char == "'":
            hex_digits = data[index + 1 : index + 3]
            try:
                decoded = bytes.fromhex(hex_digits).decode(
                    self._encoding, errors="ignore"
                )
                text_buffer.append(decoded)
            except ValueError:
                logger.debug("Invalid hex escape: %s", hex_digits)
            return index + 3

        # Non-breaking space / hyphen shortcuts
        if char == "~":
            text_buffer.append("\u00A0")
            return index + 1
        if char == "-":
            text_buffer.append("\u00AD")
            return index + 1
        if char == "_":
            text_buffer.append("\u2011")
            return index + 1

        # Read alphabetic control word
        start = index
        while index < len(data) and data[index].isalpha():
            index += 1
        word = data[start:index]

        # Parameter (optional, may include leading sign)
        sign = 1
        if index < len(data) and data[index] in "+-":
            sign = -1 if data[index] == "-" else 1
            index += 1

        param_start = index
        while index < len(data) and data[index].isdigit():
            index += 1
        param = sign * int(data[param_start:index]) if index > param_start else None

        # A space terminates the control word
        if index < len(data) and data[index] == " ":
            index += 1

        # Unicode escape
        if word == "u" and param is not None:
            text_buffer.append(self._decode_unicode(param))
            # Skip ASCII fallback character if present
            if index < len(data) and data[index] not in "{}\\":
                index += 1
            return index

        # Paragraph controls
        if word == "par":
            finalize_paragraph()
            return index
        if word == "pard":
            state.reset_character()
            state.alignment = "left"
            return index

        # Character formatting
        if word == "b":
            state.bold = param != 0
            return index
        if word == "i":
            state.italic = param != 0
            return index
        if word in {"ul", "ulnone"}:
            state.underline = word == "ul" and param != 0
            return index
        if word == "fs" and param is not None:
            state.font_size = max(1, param) / 2.0
            return index
        if word == "cf" and param is not None:
            state.color_index = max(0, param)
            return index
        if word == "plain":
            state.reset_character()
            return index
        if word == "f" and param is not None and self._font_table:
            state.font_family = self._font_table.get(param, state.font_family)
            return index

        # Alignment
        if word in {"ql", "qr", "qc", "qj"}:
            alignment_map = {
                "ql": "left",
                "qr": "right",
                "qc": "center",
                "qj": "justify",
            }
            state.alignment = alignment_map[word]
            return index

        # Special punctuation words
        if word == "emdash":
            text_buffer.append("—")
            return index
        if word == "endash":
            text_buffer.append("–")
            return index
        if word == "lquote":
            text_buffer.append("‘")
            return index
        if word == "rquote":
            text_buffer.append("’")
            return index
        if word == "ldblquote":
            text_buffer.append("“")
            return index
        if word == "rdblquote":
            text_buffer.append("”")
            return index
        if word == "tab":
            text_buffer.append("\t")
            return index
        if word == "line":
            text_buffer.append("\n")
            return index

        # Outline level hint
        if word == "outlinelevel" and param is not None:
            state.font_size = max(state.font_size, 18.0 - param)
            return index

        # Color table parsing is handled elsewhere; ignore instruction.
        return index

    def _default_state(self) -> _TextState:
        return _TextState()

    def _matches(self, data: str, index: int, token: str) -> bool:
        return data.startswith(token, index)

    def _skip_group(self, data: str, index: int) -> int:
        """Skip an entire group starting at ``index`` (which must point to '{')."""
        depth = 0
        i = index
        length = len(data)
        while i < length:
            if data[i] == "{":
                depth += 1
            elif data[i] == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
        return length

    def _decode_unicode(self, value: int) -> str:
        """Decode ``\\u`` escape values (signed 16-bit)."""
        if value < 0:
            value += 65536
        try:
            return chr(value)
        except ValueError:
            return "?"

    def _build_paragraph_style(self, runs: List[TextRun]) -> DocumentStyle:
        if not runs:
            return DocumentStyle()
        first_style = runs[0].style
        return DocumentStyle(
            font_family=first_style.font_family,
            font_size=first_style.font_size,
            bold=any(run.style.bold for run in runs),
            italic=any(run.style.italic for run in runs),
            underline=any(run.style.underline for run in runs),
            text_color=first_style.text_color,
            alignment=first_style.alignment,
        )

    def _infer_heading_level(self, style: DocumentStyle) -> Optional[int]:
        size = style.font_size or 0
        if not style.bold or size < 14:
            return None
        if size >= 26:
            return 1
        if size >= 20:
            return 2
        if size >= 16:
            return 3
        return None

    # ------------------------------------------------------------------ #
    # Metadata & resources
    # ------------------------------------------------------------------ #

    def _capture_group(self, data: str, name: str) -> Optional[str]:
        if not data:
            return None
        token = "{\\" + name
        start = data.find(token)
        if start == -1:
            return None
        return self._capture_balanced(data, start)

    def _capture_balanced(self, data: str, start: int) -> Optional[str]:
        depth = 0
        i = start
        while i < len(data):
            char = data[i]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return data[start : i + 1]
            i += 1
        return None

    def _extract_color_table(self, data: str) -> Dict[int, str]:
        colors: Dict[int, str] = {0: "#000000"}
        block = self._capture_group(data, "colortbl")
        if not block:
            return colors
        content = block.strip()[1:-1]  # remove outer braces
        content = content.replace("\\colortbl", "", 1)
        entries = content.split(";")
        for index, entry in enumerate(entries):
            entry = entry.strip()
            if not entry:
                continue
            red = self._match_int(r"\\red(\d+)", entry)
            green = self._match_int(r"\\green(\d+)", entry)
            blue = self._match_int(r"\\blue(\d+)", entry)
            if red is None or green is None or blue is None:
                continue
            colors[index] = f"#{red:02X}{green:02X}{blue:02X}"
        return colors

    def _extract_font_table(self, data: str) -> Dict[int, str]:
        fonts: Dict[int, str] = {}
        block = self._capture_group(data, "fonttbl")
        if not block:
            return fonts
        pattern = re.compile(r"{\\f(\d+)[^}]*? ([^;]+);")
        for match in pattern.finditer(block):
            try:
                idx = int(match.group(1))
                name = match.group(2).strip()
                fonts[idx] = name
            except (TypeError, ValueError):
                continue
        return fonts

    def _match_int(self, pattern: str, text: str) -> Optional[int]:
        match = re.search(pattern, text)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _parse_datetime_group(self, block: Optional[str]) -> Optional[datetime]:
        if not block:
            return None
        year = self._match_int(r"\\yr(\d+)", block)
        month = self._match_int(r"\\mo(\d+)", block) or 1
        day = self._match_int(r"\\dy(\d+)", block) or 1
        hour = self._match_int(r"\\hr(\d+)", block) or 0
        minute = self._match_int(r"\\min(\d+)", block) or 0
        second = self._match_int(r"\\sec(\d+)", block) or 0
        if not year:
            return None
        try:
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            return None

    def _parse_keywords(self, text: Optional[str]) -> List[str]:
        if not text:
            return []
        parts = re.split(r"[;,]", text)
        return [part.strip() for part in parts if part.strip()]

    # ------------------------------------------------------------------ #
    # Images
    # ------------------------------------------------------------------ #

    def _extract_images(self) -> List[Image]:
        if self._images_cache is not None:
            return self._images_cache
        self._ensure_data_loaded()
        images: List[Image] = []
        data = self._raw_text or ""
        index = 0
        while True:
            start = data.find("{\\pict", index)
            if start == -1:
                break
            block = self._capture_balanced(data, start)
            if not block:
                break
            image = self._parse_image_block(block)
            if image:
                images.append(image)
            index = start + len(block)
        self._images_cache = images
        return images

    def _parse_image_block(self, block: str) -> Optional[Image]:
        # Remove outer braces and split header/data sections
        body = block[1:-1].strip()
        newline_index = body.find("\n")
        if newline_index == -1:
            newline_index = body.find("\r")
        if newline_index == -1:
            return None

        header = body[:newline_index]
        hex_data = (
            body[newline_index:].replace("\n", "").replace("\r", "").replace(" ", "")
        )
        if not hex_data:
            return None

        mime = "application/octet-stream"
        if "\\pngblip" in header:
            mime = "image/png"
        elif "\\jpegblip" in header or "\\jpgblip" in header:
            mime = "image/jpeg"
        elif "\\dibitmap" in header:
            mime = "image/bmp"
        elif "\\wmetafile8" in header:
            mime = "image/wmf"

        try:
            data = bytes.fromhex(hex_data)
        except ValueError:
            logger.debug("Failed to decode image hex payload.")
            return None

        return Image(data=data, mime_type=mime)


# Public module exports
__all__ = ["RTFProcessor", "RTFDocument"]
