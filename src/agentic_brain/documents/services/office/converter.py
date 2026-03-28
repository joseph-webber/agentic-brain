"""Office document format converter for agentic-brain."""

from __future__ import annotations

import logging
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Union

from .models import DocumentContent, OfficeFormat, Paragraph, TextRun

logger = logging.getLogger(__name__)

# Optional dependencies ------------------------------------------------------

try:  # python-docx
    from docx import Document as DocxDocument

    HAS_PYTHON_DOCX = True
except ImportError:  # pragma: no cover - optional dependency
    DocxDocument = None
    HAS_PYTHON_DOCX = False

try:  # mammoth for high fidelity DOCX -> HTML/Markdown
    import mammoth

    HAS_MAMMOTH = True
except ImportError:  # pragma: no cover - optional dependency
    mammoth = None
    HAS_MAMMOTH = False

try:  # html2text for HTML -> Markdown fallback
    import html2text

    HAS_HTML2TEXT = True
except ImportError:  # pragma: no cover - optional dependency
    html2text = None
    HAS_HTML2TEXT = False

try:  # docx2pdf for fast PDF conversion on macOS/Windows
    import docx2pdf

    HAS_DOCX2PDF = True
except ImportError:  # pragma: no cover - optional dependency
    docx2pdf = None
    HAS_DOCX2PDF = False

try:  # openpyxl for spreadsheet parsing
    import openpyxl

    HAS_OPENPYXL = True
except ImportError:  # pragma: no cover - optional dependency
    openpyxl = None
    HAS_OPENPYXL = False

try:  # python-pptx for presentation parsing
    from pptx import Presentation as PptxPresentation

    HAS_PPTX = True
except ImportError:  # pragma: no cover - optional dependency
    PptxPresentation = None
    HAS_PPTX = False

class ConversionError(RuntimeError):
    """Raised when a conversion workflow fails."""


class OfficeConverter:
    """Cross-format Office document converter."""

    WORD_LIKE_EXTENSIONS = {"docx", "doc", "rtf", "odt"}
    EXCEL_LIKE_EXTENSIONS = {"xlsx", "xls", "ods", "csv"}
    POWERPOINT_LIKE_EXTENSIONS = {"pptx", "ppt", "odp"}
    IWORK_EXTENSIONS = {"pages", "numbers", "key", "keynote"}

    FORMAT_ALIAS: Dict[str, OfficeFormat] = {
        "docx": OfficeFormat.DOCX,
        "doc": OfficeFormat.DOCX,
        "rtf": OfficeFormat.RTF,
        "odt": OfficeFormat.ODT,
        "xlsx": OfficeFormat.XLSX,
        "xls": OfficeFormat.XLSX,
        "ods": OfficeFormat.ODS,
        "csv": OfficeFormat.ODS,  # treat CSV as spreadsheet content
        "pptx": OfficeFormat.PPTX,
        "ppt": OfficeFormat.PPTX,
        "odp": OfficeFormat.ODP,
        "pages": OfficeFormat.PAGES,
        "numbers": OfficeFormat.NUMBERS,
        "key": OfficeFormat.KEYNOTE,
        "keynote": OfficeFormat.KEYNOTE,
    }

    def __init__(self, libreoffice_path: Optional[Union[str, Path]] = None, timeout: int = 120) -> None:
        self.platform = platform.system()
        self.timeout = timeout
        self.libreoffice_path = (
            Path(libreoffice_path).expanduser()
            if libreoffice_path
            else self._auto_detect_libreoffice()
        )
        self.textutil_path = (
            Path(shutil.which("textutil")).resolve()  # type: ignore[arg-type]
            if self.platform == "Darwin" and shutil.which("textutil")
            else None
        )

        if not self.libreoffice_path:
            logger.debug("LibreOffice not detected. Some conversions will be limited.")
        if self.platform == "Darwin" and not self.textutil_path:
            logger.debug("textutil not available. iWork conversions will rely on LibreOffice.")

    # ------------------------------------------------------------------ Public API

    def to_pdf(self, input_path: Union[str, Path], output_path: Optional[Union[str, Path]] = None) -> Path:
        """Convert a document into PDF."""

        source = self._normalize_input(input_path)
        target = self._prepare_output(source, output_path, suffix=".pdf")
        extension = source.suffix.lstrip(".").lower()

        logger.debug("Converting %s -> %s (pdf)", source, target)

        if extension in self.WORD_LIKE_EXTENSIONS:
            if self._can_use_docx2pdf():
                try:
                    return self._convert_with_docx2pdf(source, target)
                except ConversionError as exc:
                    logger.debug("docx2pdf failed (%s); falling back to LibreOffice", exc)
            return self._convert_with_libreoffice(source, target, "pdf")

        if extension in self.IWORK_EXTENSIONS and self.textutil_path:
            try:
                return self._convert_with_textutil(source, target, "pdf")
            except ConversionError as exc:
                logger.debug("textutil failed (%s); falling back to LibreOffice", exc)

        # Excel / PowerPoint / OpenDocument or any other supported format
        return self._convert_with_libreoffice(source, target, "pdf")

    def to_text(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        *,
        encoding: str = "utf-8",
    ) -> Path:
        """Extract structured plain text and persist it to ``*.txt``."""

        source = self._normalize_input(input_path)
        target = self._prepare_output(source, output_path, suffix=".txt")

        text_content, _ = self._extract_textual_content(source)
        target.write_text(text_content, encoding=encoding)

        logger.info("Extracted text from %s -> %s", source.name, target.name)
        self._maybe_emit_debug_preview(text_content)

        return target

    def to_html(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        *,
        encoding: str = "utf-8",
    ) -> Path:
        """Convert document to HTML."""

        source = self._normalize_input(input_path)
        target = self._prepare_output(source, output_path, suffix=".html")
        extension = source.suffix.lstrip(".").lower()

        if extension == "docx" and HAS_MAMMOTH:
            html_content = self._convert_docx_with_mammoth(source, to_markdown=False)
            target.write_text(html_content, encoding=encoding)
            return target

        if extension in self.IWORK_EXTENSIONS and self.textutil_path:
            html_content = self._convert_textutil_to_string(source, "html")
            target.write_text(html_content, encoding=encoding)
            return target

        # Fallback to LibreOffice export
        return self._convert_with_libreoffice(source, target, "html")

    def to_markdown(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        *,
        encoding: str = "utf-8",
    ) -> Path:
        """Convert document to Markdown using mammoth or HTML fallbacks."""

        source = self._normalize_input(input_path)
        target = self._prepare_output(source, output_path, suffix=".md")
        extension = source.suffix.lstrip(".").lower()

        if extension == "docx" and HAS_MAMMOTH:
            markdown_content = self._convert_docx_with_mammoth(source, to_markdown=True)
            target.write_text(markdown_content, encoding=encoding)
            return target

        html_source: Optional[Path] = None
        html_text: Optional[str] = None

        if extension in self.IWORK_EXTENSIONS and self.textutil_path:
            html_text = self._convert_textutil_to_string(source, "html")
        else:
            html_source = self._temporary_conversion(source, "html")
            html_text = html_source.read_text(encoding="utf-8", errors="ignore")

        markdown_content = self._html_to_markdown(html_text)
        target.write_text(markdown_content, encoding=encoding)

        if html_source:
            html_source.unlink(missing_ok=True)

        return target

    def batch_convert(
        self,
        input_files: Sequence[Union[str, Path]],
        target_format: str,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> List[Path]:
        """Convert multiple files to the same target format."""

        fmt = target_format.lower()
        method_map: Dict[str, Tuple[Callable[..., Path], str]] = {
            "pdf": (self.to_pdf, ".pdf"),
            "html": (self.to_html, ".html"),
            "markdown": (self.to_markdown, ".md"),
            "md": (self.to_markdown, ".md"),
            "text": (self.to_text, ".txt"),
            "txt": (self.to_text, ".txt"),
        }

        if fmt not in method_map:
            raise ValueError(f"Unsupported batch target format: {target_format}")

        method, suffix = method_map[fmt]
        outputs: List[Path] = []
        output_dir_path = Path(output_dir).expanduser() if output_dir else None
        if output_dir_path:
            output_dir_path.mkdir(parents=True, exist_ok=True)

        for file_path in input_files:
            try:
                source = self._normalize_input(file_path)
            except FileNotFoundError:
                logger.warning("Skipping missing file: %s", file_path)
                continue

            destination = (
                output_dir_path / f"{source.stem}{suffix}" if output_dir_path else None
            )

            try:
                result_path = method(source, destination)
                outputs.append(result_path)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("Failed to convert %s: %s", source.name, exc)

        logger.info(
            "Batch conversion complete: %d/%d succeeded",
            len(outputs),
            len(input_files),
        )
        return outputs

    # ------------------------------------------------------------------ Core helpers

    def _extract_textual_content(self, source: Path) -> Tuple[str, DocumentContent]:
        """Return text content alongside a lightweight DocumentContent."""

        extension = source.suffix.lstrip(".").lower()

        if extension in self.WORD_LIKE_EXTENSIONS:
            text = self._extract_word_text(source)
        elif extension in self.EXCEL_LIKE_EXTENSIONS:
            text = self._extract_spreadsheet_text(source)
        elif extension in self.POWERPOINT_LIKE_EXTENSIONS:
            text = self._extract_presentation_text(source)
        elif extension in self.IWORK_EXTENSIONS:
            text = self._extract_iwork_text(source)
        else:
            text = self._extract_via_libreoffice_text(source)

        document = DocumentContent(
            format=self.FORMAT_ALIAS.get(extension, OfficeFormat.DOCX),
            paragraphs=[
                Paragraph(runs=[TextRun(text=line)])
                for line in text.splitlines()
                if line.strip()
            ],
        )
        return text, document

    def _extract_word_text(self, source: Path) -> str:
        """Extract text using python-docx with LibreOffice fallback."""

        if not HAS_PYTHON_DOCX:
            logger.debug("python-docx unavailable; using LibreOffice for text extraction")
            return self._extract_via_libreoffice_text(source)

        doc = DocxDocument(str(source))
        lines: List[str] = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                lines.append(text)

        for table in doc.tables:
            for row in table.rows:
                row_text = "\t".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    lines.append(row_text)

        return "\n".join(lines)

    def _extract_spreadsheet_text(self, source: Path) -> str:
        """Extract text from spreadsheet formats using openpyxl."""

        if not HAS_OPENPYXL:
            logger.debug("openpyxl unavailable; using LibreOffice for text extraction")
            return self._extract_via_libreoffice_text(source)

        workbook = openpyxl.load_workbook(str(source), data_only=True, read_only=True)
        lines: List[str] = []

        for sheet in workbook.worksheets:
            lines.append(f"[{sheet.title}]")
            for row in sheet.iter_rows(values_only=True):
                if all(cell is None or str(cell).strip() == "" for cell in row):
                    continue
                row_text = "\t".join("" if cell is None else str(cell) for cell in row)
                lines.append(row_text)

        workbook.close()
        return "\n".join(lines)

    def _extract_presentation_text(self, source: Path) -> str:
        """Extract text from PPT/PPTX using python-pptx."""

        if not HAS_PPTX:
            logger.debug("python-pptx unavailable; using LibreOffice for text extraction")
            return self._extract_via_libreoffice_text(source)

        presentation = PptxPresentation(str(source))
        lines: List[str] = []

        for index, slide in enumerate(presentation.slides, start=1):
            lines.append(f"Slide {index}")
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text = getattr(shape, "text", "").strip()
                    if text:
                        lines.append(text)

        return "\n".join(lines)

    def _extract_iwork_text(self, source: Path) -> str:
        """Extract text from iWork formats via textutil on macOS."""

        if self.textutil_path:
            return self._convert_textutil_to_string(source, "txt")

        logger.debug("textutil unavailable; using LibreOffice for iWork text extraction")
        return self._extract_via_libreoffice_text(source)

    def _extract_via_libreoffice_text(self, source: Path) -> str:
        """Generic LibreOffice TXT extraction used as a fallback."""

        temp_txt = self._temporary_conversion(source, "txt")
        try:
            return temp_txt.read_text(encoding="utf-8", errors="ignore")
        finally:
            temp_txt.unlink(missing_ok=True)

    def _convert_with_docx2pdf(self, source: Path, target: Path) -> Path:
        """Use docx2pdf for Word conversions on macOS/Windows."""

        if not HAS_DOCX2PDF:
            raise ConversionError("docx2pdf is not installed.")
        if self.platform not in {"Windows", "Darwin"}:
            raise ConversionError("docx2pdf only supports Windows/macOS.")

        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            docx2pdf.convert(str(source), str(target))
        except Exception as exc:  # pragma: no cover - external dependency
            raise ConversionError(f"docx2pdf failed: {exc}") from exc
        return target

    def _convert_with_libreoffice(self, source: Path, target: Path, target_format: str) -> Path:
        """Invoke LibreOffice headless mode for conversion."""

        if not self.libreoffice_path:
            raise ConversionError("LibreOffice binary not found.")

        target.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            str(self.libreoffice_path),
            "--headless",
            "--convert-to",
            target_format,
            "--outdir",
            str(target.parent),
            str(source),
        ]

        logger.debug("Running LibreOffice command: %s", " ".join(cmd))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )

        if result.returncode != 0:
            raise ConversionError(result.stderr or result.stdout or "LibreOffice conversion failed.")

        produced = target.parent / f"{source.stem}.{target_format.split(':', 1)[0]}"
        if produced != target:
            if produced.exists():
                produced.replace(target)
            else:
                raise ConversionError(f"Expected output not produced: {produced}")

        return target

    def _convert_with_textutil(self, source: Path, target: Path, target_format: str) -> Path:
        """Use macOS textutil for Pages/Numbers/Keynote exports."""

        if not self.textutil_path:
            raise ConversionError("textutil not available on this platform.")

        target.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            str(self.textutil_path),
            "-convert",
            target_format,
            str(source),
            "-output",
            str(target),
        ]

        logger.debug("Running textutil command: %s", " ".join(cmd))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )

        if result.returncode != 0:
            raise ConversionError(result.stderr or result.stdout or "textutil conversion failed.")

        if not target.exists():
            raise ConversionError(f"textutil reported success but {target} is missing.")

        return target

    def _convert_textutil_to_string(self, source: Path, target_format: str) -> str:
        """Convert using textutil and return the produced text without persisting."""

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir) / f"{source.stem}.{target_format}"
            self._convert_with_textutil(source, temp_path, target_format)
            return temp_path.read_text(encoding="utf-8", errors="ignore")

    def _convert_docx_with_mammoth(self, source: Path, *, to_markdown: bool) -> str:
        """Use mammoth for DOCX -> HTML/Markdown conversion."""

        if not HAS_MAMMOTH:
            raise ConversionError("mammoth is not installed.")

        with source.open("rb") as handle:
            if to_markdown:
                result = mammoth.convert_to_markdown(handle)
            else:
                result = mammoth.convert_to_html(handle)

        for message in result.messages:  # pragma: no cover - best effort logging
            logger.debug("mammoth notice: %s", message)

        return result.value

    def _temporary_conversion(self, source: Path, target_format: str) -> Path:
        """Perform a temporary LibreOffice conversion and return the temp file path."""

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_target = Path(tmp_dir) / f"{source.stem}.{target_format}"
            self._convert_with_libreoffice(source, temp_target, target_format)
            # Copy to a persistent temp path because TemporaryDirectory cleans up immediately
            fd, temp_name = tempfile.mkstemp(suffix=f".{target_format}")
            os.close(fd)
            persistent_temp = Path(temp_name)
            shutil.copy(temp_target, persistent_temp)
        return persistent_temp

    # ------------------------------------------------------------------ Utilities

    def _normalize_input(self, input_path: Union[str, Path]) -> Path:
        """Validate and normalise the incoming path."""

        path = Path(input_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")
        return path

    def _prepare_output(
        self,
        source: Path,
        output_path: Optional[Union[str, Path]],
        *,
        suffix: str,
    ) -> Path:
        """Return a writable output path, creating parent directories as needed."""

        target = Path(output_path).expanduser() if output_path else source.with_suffix(suffix)
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def _auto_detect_libreoffice(self) -> Optional[Path]:
        """Best-effort detection of the LibreOffice binary."""

        candidates: List[Path] = []
        if self.platform == "Darwin":
            candidates = [
                Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
                Path("/usr/local/bin/soffice"),
                Path("/opt/homebrew/bin/soffice"),
            ]
        elif self.platform == "Linux":
            candidates = [
                Path("/usr/bin/soffice"),
                Path("/usr/bin/libreoffice"),
                Path("/usr/local/bin/soffice"),
            ]
        elif self.platform == "Windows":
            candidates = [
                Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
                Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
            ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        env_path = shutil.which("soffice")
        return Path(env_path).resolve() if env_path else None

    def _can_use_docx2pdf(self) -> bool:
        """Return True when docx2pdf is usable on the current platform."""

        return HAS_DOCX2PDF and self.platform in {"Windows", "Darwin"}

    def _html_to_markdown(self, html: str) -> str:
        """Convert HTML to Markdown using html2text if available."""

        if HAS_HTML2TEXT:
            parser = html2text.HTML2Text()
            parser.ignore_links = False
            parser.ignore_images = False
            parser.body_width = 0
            return parser.handle(html)

        # Lightweight fallback: strip tags and normalise whitespace
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _maybe_emit_debug_preview(self, text: str, limit: int = 400) -> None:
        """Log a short preview of extracted text for debugging."""

        preview = text.strip().splitlines()[:10]
        if preview:
            logger.debug("Text preview:\n%s", "\n".join(preview)[:limit])


__all__ = ["OfficeConverter", "ConversionError"]
