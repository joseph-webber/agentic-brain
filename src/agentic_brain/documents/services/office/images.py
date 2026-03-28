# SPDX-License-Identifier: Apache-2.0

"""Unified image extraction utilities for Office-style document containers."""

from __future__ import annotations

import base64
import hashlib
import io
import mimetypes
import posixpath
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from xml.etree import ElementTree as ET

from .exceptions import UnsupportedOfficeFormatError

try:
    from PIL import Image as PILImage
except Exception:  # pragma: no cover - pillow is optional
    PILImage = None


WORD_NAMESPACES = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

SPREADSHEET_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": WORD_NAMESPACES["r"],
}

PRESENTATION_NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": WORD_NAMESPACES["a"],
    "r": WORD_NAMESPACES["r"],
    "pic": WORD_NAMESPACES["pic"],
}

REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _emu_to_px(value: Optional[str]) -> Optional[int]:
    """Convert English Metric Units (EMU) to pixel units."""
    if value is None:
        return None
    try:
        return int(round(int(value) / 9525))
    except (TypeError, ValueError):
        return None


def _safe_float(value: Optional[str]) -> float:
    """Convert strings to float with graceful fallback."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dataclass(slots=True)
class Image:
    """In-memory representation of an embedded image."""

    data: bytes
    filename: str
    mime_type: str
    width: Optional[int] = None
    height: Optional[int] = None
    position: Tuple[Optional[int], float, float] = field(
        default_factory=lambda: (None, 0.0, 0.0)
    )
    alt_text: Optional[str] = None
    caption: Optional[str] = None

    def save(self, path: str | Path) -> Path:
        """Persist the image to disk."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.data)
        return target

    def to_base64(self) -> str:
        """Return base64-encoded representation."""
        return base64.b64encode(self.data).decode("ascii")

    def get_thumbnail(self, max_size: int = 256) -> bytes:
        """Return thumbnail bytes (PNG) with constrained max dimension."""
        if PILImage is None:
            raise RuntimeError("Thumbnail generation requires Pillow")
        with PILImage.open(io.BytesIO(self.data)) as pil_img:
            pil_img.thumbnail((max_size, max_size))
            buffer = io.BytesIO()
            pil_img.save(buffer, format="PNG")
        return buffer.getvalue()

    def get_format(self) -> str:
        """Return canonical short format (png, jpeg, etc.)."""
        if self.mime_type:
            subtype = self.mime_type.split("/")[-1]
            if subtype:
                return subtype.replace("jpeg", "jpg")
        suffix = Path(self.filename).suffix.lower().lstrip(".")
        return suffix or "bin"

    def get_hash(self) -> str:
        """Return deterministic hash of image content."""
        return hashlib.sha256(self.data).hexdigest()


class ImageExtractor:
    """High-level service for extracting images from office documents."""

    def __init__(self) -> None:
        self._handlers = {
            "docx": self.extract_images_from_docx,
            "xlsx": self.extract_images_from_xlsx,
            "pptx": self.extract_images_from_pptx,
            "pages": self.extract_images_from_pages,
            "key": self.extract_images_from_keynote,
            "keynote": self.extract_images_from_keynote,
            "numbers": self.extract_images_from_keynote,
            "odt": self.extract_images_from_odt,
        }

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def extract_images(self, path: str | Path) -> List[Image]:
        """Auto-detect format and return extracted images."""
        fmt = self._detect_format(path)
        handler = self._handlers.get(fmt)
        if handler is None:
            raise UnsupportedOfficeFormatError(fmt)
        return handler(path)

    def extract_images_from_docx(self, path: str | Path) -> List[Image]:
        """Extract images embedded within a DOCX container."""
        return self._extract_word_images(Path(path), "word")

    def extract_images_from_xlsx(self, path: str | Path) -> List[Image]:
        """Extract worksheet images with location metadata."""
        archive_path = Path(path)
        images: List[Image] = []
        with zipfile.ZipFile(archive_path) as zip_file:
            drawing_to_sheet = self._map_xlsx_drawings(zip_file)
            for drawing_path, sheet_info in drawing_to_sheet.items():
                metadata = self._parse_xlsx_drawing_metadata(
                    zip_file, drawing_path, sheet_info
                )
                rels = self._parse_relationships(
                    zip_file, self._rels_path(drawing_path)
                )
                for rid, target in rels.items():
                    if not target.startswith("xl/media/"):
                        continue
                    meta = metadata.get(rid, {})
                    image = self._read_zip_image(zip_file, target, meta, sheet_info)
                    if image:
                        images.append(image)
            if not images:
                images.extend(
                    self._extract_simple_media(zip_file, "xl/media/", sheet_index=None)
                )
        return images

    def extract_images_from_pptx(self, path: str | Path) -> List[Image]:
        """Extract slide images from a PPTX archive."""
        archive_path = Path(path)
        images: List[Image] = []
        with zipfile.ZipFile(archive_path) as zip_file:
            slide_paths = sorted(
                p for p in zip_file.namelist() if p.startswith("ppt/slides/slide")
            )
            for index, slide_path in enumerate(slide_paths, start=1):
                metadata = self._parse_pptx_slide_metadata(zip_file, slide_path, index)
                rels = self._parse_relationships(zip_file, self._rels_path(slide_path))
                for rid, target in rels.items():
                    if not target.startswith("ppt/media/"):
                        continue
                    meta = metadata.get(rid, {})
                    image = self._read_zip_image(
                        zip_file, target, meta, slide_index=index
                    )
                    if image:
                        images.append(image)
            if not images:
                images.extend(
                    self._extract_simple_media(zip_file, "ppt/media/", sheet_index=None)
                )
        return images

    def extract_images_from_pages(self, path: str | Path) -> List[Image]:
        """Extract embedded assets from Apple Pages documents."""
        return self._extract_iwork_archive(Path(path))

    def extract_images_from_keynote(self, path: str | Path) -> List[Image]:
        """Extract embedded images from Keynote/Numbers packages."""
        return self._extract_iwork_archive(Path(path))

    def extract_images_from_odt(self, path: str | Path) -> List[Image]:
        """Extract OpenDocument Text embedded images."""
        archive_path = Path(path)
        with zipfile.ZipFile(archive_path) as zip_file:
            return self._extract_simple_media(zip_file, "Pictures/", sheet_index=None)

    def extract_all_images(
        self, paths: Sequence[str | Path], output_dir: str | Path
    ) -> Dict[str, List[str]]:
        """Batch extraction helper returning saved file paths."""
        results: Dict[str, List[str]] = {}
        for path in paths:
            saved = self.save_all_images(path, output_dir)
            results[str(path)] = saved
        return results

    def save_all_images(self, path: str | Path, output_dir: str | Path) -> List[str]:
        """Extract images for a single document and write them to disk."""
        images = self.extract_images(path)
        return self._persist_images(images, Path(output_dir), Path(path))

    # ------------------------------------------------------------------ #
    # Deduplication helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def find_duplicates(images: Sequence[Image]) -> List[List[Image]]:
        """Group identical images by content hash."""
        buckets: Dict[str, List[Image]] = {}
        for image in images:
            buckets.setdefault(image.get_hash(), []).append(image)
        return [group for group in buckets.values() if len(group) > 1]

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _detect_format(self, path: str | Path) -> str:
        suffix = Path(path).suffix.lower().lstrip(".")
        if suffix in self._handlers:
            return suffix
        if suffix in {"key", "numbers"}:
            return "key"
        return suffix

    def _extract_word_images(self, doc_path: Path, root: str) -> List[Image]:
        images: List[Image] = []
        with zipfile.ZipFile(doc_path) as zip_file:
            rels = self._parse_relationships(
                zip_file, f"{root}/_rels/document.xml.rels"
            )
            metadata = self._parse_docx_metadata(zip_file)
            for rid, target in rels.items():
                if not target.startswith(f"{root}/media/"):
                    continue
                meta = metadata.get(rid, {})
                image = self._read_zip_image(zip_file, target, meta, page_index=None)
                if image:
                    images.append(image)
            if not images:
                images.extend(
                    self._extract_simple_media(
                        zip_file, f"{root}/media/", sheet_index=None
                    )
                )
        return images

    def _parse_docx_metadata(
        self, zip_file: zipfile.ZipFile
    ) -> Dict[str, Dict[str, object]]:
        """Return metadata keyed by relationship id."""
        try:
            xml_bytes = zip_file.read("word/document.xml")
        except KeyError:
            return {}
        root = ET.fromstring(xml_bytes)
        metadata: Dict[str, Dict[str, object]] = {}
        for index, drawing in enumerate(
            root.findall(".//w:drawing", WORD_NAMESPACES), start=1
        ):
            blip = drawing.find(".//a:blip", WORD_NAMESPACES)
            if blip is None:
                continue
            rid = blip.attrib.get(f"{{{WORD_NAMESPACES['r']}}}embed")
            if rid is None:
                continue
            doc_pr = drawing.find(".//wp:docPr", WORD_NAMESPACES)
            extent = drawing.find(".//wp:extent", WORD_NAMESPACES)
            anchor = drawing.find(".//wp:positionH/wp:posOffset", WORD_NAMESPACES)
            anchor_v = drawing.find(".//wp:positionV/wp:posOffset", WORD_NAMESPACES)
            width = _emu_to_px(extent.attrib.get("cx") if extent is not None else None)
            height = _emu_to_px(extent.attrib.get("cy") if extent is not None else None)
            x = _emu_to_px(anchor.text if anchor is not None else None) or 0
            y = _emu_to_px(anchor_v.text if anchor_v is not None else None) or 0
            metadata[rid] = {
                "alt_text": (doc_pr.attrib.get("descr") if doc_pr is not None else None)
                or (doc_pr.attrib.get("title") if doc_pr is not None else None),
                "caption": doc_pr.attrib.get("title") if doc_pr is not None else None,
                "width": width,
                "height": height,
                "position": (None, float(x), float(y)),
                "page_index": index,
            }
        return metadata

    def _map_xlsx_drawings(
        self, zip_file: zipfile.ZipFile
    ) -> Dict[str, Dict[str, object]]:
        """Map drawing parts to sheet names and indices."""
        workbook = self._read_xml(zip_file, "xl/workbook.xml")
        if workbook is None:
            return {}
        workbook_rels = self._parse_relationships(
            zip_file, "xl/_rels/workbook.xml.rels"
        )
        sheets = workbook.findall("main:sheets/main:sheet", SPREADSHEET_NS)
        drawing_map: Dict[str, Dict[str, object]] = {}
        for sheet_index, sheet in enumerate(sheets, start=1):
            rid = sheet.attrib.get(f"{{{SPREADSHEET_NS['r']}}}id")
            name = sheet.attrib.get("name", f"Sheet{sheet_index}")
            sheet_part = workbook_rels.get(rid)
            if not sheet_part:
                continue
            drawing_paths = self._sheet_drawings(zip_file, sheet_part)
            for drawing_path in drawing_paths:
                drawing_map[drawing_path] = {
                    "sheet_index": sheet_index,
                    "sheet_name": name,
                }
        return drawing_map

    def _sheet_drawings(self, zip_file: zipfile.ZipFile, sheet_path: str) -> List[str]:
        """Return drawing part paths referenced by a worksheet."""
        rel_path = self._rels_path(sheet_path)
        rels = self._parse_relationships(zip_file, rel_path)
        return [target for target in rels.values() if "drawings" in target]

    def _parse_xlsx_drawing_metadata(
        self,
        zip_file: zipfile.ZipFile,
        drawing_path: str,
        sheet_info: Dict[str, object],
    ) -> Dict[str, Dict[str, object]]:
        """Parse anchors and metadata from a drawing part."""
        drawing = self._read_xml(zip_file, drawing_path)
        if drawing is None:
            return {}
        metadata: Dict[str, Dict[str, object]] = {}
        anchors = drawing.findall(
            "xdr:twoCellAnchor", SPREADSHEET_NS
        ) + drawing.findall("xdr:oneCellAnchor", SPREADSHEET_NS)
        for anchor in anchors:
            pic = anchor.find("xdr:pic", SPREADSHEET_NS)
            if pic is None:
                continue
            blip = pic.find(".//a:blip", SPREADSHEET_NS)
            if blip is None:
                continue
            rid = blip.attrib.get(f"{{{SPREADSHEET_NS['r']}}}embed")
            if rid is None:
                continue
            doc_pr = pic.find(".//xdr:cNvPr", SPREADSHEET_NS)
            ext = pic.find(".//a:ext", SPREADSHEET_NS)
            width = _emu_to_px(ext.attrib.get("cx") if ext is not None else None)
            height = _emu_to_px(ext.attrib.get("cy") if ext is not None else None)
            anchor_from = anchor.find("xdr:from", SPREADSHEET_NS)
            col = anchor_from.findtext(
                "xdr:col", default="0", namespaces=SPREADSHEET_NS
            )
            row = anchor_from.findtext(
                "xdr:row", default="0", namespaces=SPREADSHEET_NS
            )
            metadata[rid] = {
                "alt_text": doc_pr.attrib.get("descr") if doc_pr is not None else None,
                "caption": doc_pr.attrib.get("name") if doc_pr is not None else None,
                "width": width,
                "height": height,
                "position": (
                    sheet_info.get("sheet_index"),
                    float(col),
                    float(row),
                ),
            }
        return metadata

    def _parse_pptx_slide_metadata(
        self, zip_file: zipfile.ZipFile, slide_path: str, slide_index: int
    ) -> Dict[str, Dict[str, object]]:
        """Parse picture metadata for a single slide."""
        slide = self._read_xml(zip_file, slide_path)
        if slide is None:
            return {}
        metadata: Dict[str, Dict[str, object]] = {}
        pictures = slide.findall(".//p:pic", PRESENTATION_NS)
        for pic in pictures:
            blip = pic.find(".//a:blip", PRESENTATION_NS)
            if blip is None:
                continue
            rid = blip.attrib.get(f"{{{PRESENTATION_NS['r']}}}embed")
            if rid is None:
                continue
            doc_pr = pic.find(".//p:cNvPr", PRESENTATION_NS)
            off = pic.find(".//a:off", PRESENTATION_NS)
            ext = pic.find(".//a:ext", PRESENTATION_NS)
            width = _emu_to_px(ext.attrib.get("cx") if ext is not None else None)
            height = _emu_to_px(ext.attrib.get("cy") if ext is not None else None)
            x = _emu_to_px(off.attrib.get("x") if off is not None else None) or 0
            y = _emu_to_px(off.attrib.get("y") if off is not None else None) or 0
            metadata[rid] = {
                "alt_text": doc_pr.attrib.get("descr") if doc_pr is not None else None,
                "caption": doc_pr.attrib.get("name") if doc_pr is not None else None,
                "width": width,
                "height": height,
                "position": (slide_index, float(x), float(y)),
            }
        return metadata

    def _extract_iwork_archive(self, archive_path: Path) -> List[Image]:
        """Handle Apple Pages/Keynote/Numbers archives."""
        with zipfile.ZipFile(archive_path) as zip_file:
            target_prefix = "Data/"
            if not any(name.startswith(target_prefix) for name in zip_file.namelist()):
                target_prefix = "QuickLook/"
            return self._extract_simple_media(zip_file, target_prefix, sheet_index=None)

    def _extract_simple_media(
        self,
        zip_file: zipfile.ZipFile,
        prefix: str,
        sheet_index: Optional[int],
    ) -> List[Image]:
        """Fallback extractor scanning media folder contents."""
        images: List[Image] = []
        for member in zip_file.namelist():
            if not member.startswith(prefix):
                continue
            if member.endswith("/"):
                continue
            image = self._read_zip_image(
                zip_file,
                member,
                meta={"position": (sheet_index, 0.0, 0.0)},
                page_index=sheet_index,
            )
            if image:
                images.append(image)
        return images

    def _read_zip_image(
        self,
        zip_file: zipfile.ZipFile,
        member: str,
        meta: Dict[str, object],
        sheet_index: Optional[int] = None,
        page_index: Optional[int] = None,
        slide_index: Optional[int] = None,
    ) -> Optional[Image]:
        """Instantiate Image from archive member."""
        try:
            data = zip_file.read(member)
        except KeyError:
            return None
        filename = PurePosixPath(member).name
        mime_type, _ = mimetypes.guess_type(filename)
        width = meta.get("width")
        height = meta.get("height")
        width, height = self._ensure_dimensions(data, width, height)
        position = meta.get("position")
        if position is None:
            index = (
                page_index
                if page_index is not None
                else slide_index if slide_index is not None else sheet_index
            )
            position = (index, 0.0, 0.0)
        return Image(
            data=data,
            filename=filename,
            mime_type=mime_type or "application/octet-stream",
            width=width,
            height=height,
            position=position,  # type: ignore[arg-type]
            alt_text=meta.get("alt_text"),
            caption=meta.get("caption"),
        )

    def _ensure_dimensions(
        self, data: bytes, width: Optional[int], height: Optional[int]
    ) -> Tuple[Optional[int], Optional[int]]:
        """Populate missing width/height via Pillow if available."""
        if width is not None and height is not None:
            return width, height
        if PILImage is None:
            return width, height
        try:
            with PILImage.open(io.BytesIO(data)) as pil_img:
                width = width or pil_img.width
                height = height or pil_img.height
        except Exception:  # pragma: no cover - corrupted image fallback
            return width, height
        return width, height

    # XML/ZIP helpers --------------------------------------------------- #
    def _parse_relationships(
        self, zip_file: zipfile.ZipFile, rels_path: str
    ) -> Dict[str, str]:
        """Parse .rels files into relationship targets."""
        try:
            xml = zip_file.read(rels_path)
        except KeyError:
            return {}
        base_dir = self._relationship_base_dir(rels_path)
        root = ET.fromstring(xml)
        relationships: Dict[str, str] = {}
        for rel in root.findall(f".//{{{REL_NS}}}Relationship"):
            rid = rel.attrib.get("Id")
            target = rel.attrib.get("Target")
            mode = rel.attrib.get("TargetMode", "Internal")
            if mode != "Internal" or not rid or not target:
                continue
            resolved = self._resolve_target(base_dir, target)
            relationships[rid] = resolved
        return relationships

    @staticmethod
    def _relationship_base_dir(rels_path: str) -> str:
        """Determine base directory for relationship resolution."""
        rel = PurePosixPath(rels_path)
        if rel.parent.name == "_rels":
            base = rel.parent.parent
        else:
            base = rel.parent
        doc_name = rel.stem
        document = base / doc_name
        return str(document.parent)

    @staticmethod
    def _resolve_target(base_dir: str, target: str) -> str:
        """Resolve relative relationship target paths."""
        if target.startswith("/"):
            return target.lstrip("/")
        combined = PurePosixPath(base_dir) / target
        return posixpath.normpath(str(combined))

    @staticmethod
    def _rels_path(part_path: str) -> str:
        """Return the .rels counterpart for a package part."""
        part = PurePosixPath(part_path)
        rel_dir = part.parent / "_rels"
        rel_name = f"{part.name}.rels"
        return str(rel_dir / rel_name)

    @staticmethod
    def _read_xml(zip_file: zipfile.ZipFile, member: str) -> Optional[ET.Element]:
        """Read XML member and return parsed root."""
        try:
            data = zip_file.read(member)
        except KeyError:
            return None
        return ET.fromstring(data)

    def _persist_images(
        self, images: Sequence[Image], output_dir: Path, source: Path
    ) -> List[str]:
        """Write image collection to disk with deterministic naming."""
        output_dir.mkdir(parents=True, exist_ok=True)
        saved_paths: List[str] = []
        base = source.stem or "document"
        for index, image in enumerate(images, start=1):
            ext = image.get_format()
            candidate = output_dir / f"{base}_image_{index}.{ext}"
            suffix = 1
            while candidate.exists():
                candidate = output_dir / f"{base}_image_{index}_{suffix}.{ext}"
                suffix += 1
            image.save(candidate)
            saved_paths.append(str(candidate))
        return saved_paths

