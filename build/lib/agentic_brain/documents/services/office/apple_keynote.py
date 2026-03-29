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

"""Apple Keynote presentation processor for agentic-brain.

The modern Keynote ``.key`` format is an iWork ZIP package containing ``.iwa``
protobuf archives, embedded assets, and preview images. Apple does not publish
the full protobuf schema for every internal archive, so this processor uses a
layered strategy:

1. Native ZIP package inspection for metadata, previews, images, videos, and
   per-slide ``.iwa`` archives.
2. Heuristic IWA parsing using optional Snappy decompression and generic
   protobuf scanning to recover slide text, speaker notes, and presentation
   metadata without requiring Apple's private schemas.
3. macOS fallbacks for environments where Keynote itself is available:
   ``textutil`` for plain-text extraction and AppleScript automation for
   richer slide extraction and PDF export.

The implementation focuses on robust read/extract workflows rather than exact
round-trip fidelity. Slide transitions, builds, animations, master slide names,
and embedded videos are surfaced as metadata when they can be inferred.
"""

from __future__ import annotations

import logging
import mimetypes
import platform
import plistlib
import re
import shutil
import subprocess
import warnings
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

try:
    import snappy

    SNAPPY_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    SNAPPY_AVAILABLE = False
    warnings.warn(
        "python-snappy not available. Install with: pip install python-snappy",
        stacklevel=2,
    )

from .exceptions import DocumentValidationError, InvalidDocumentStructureError
from .models import (
    DocumentContent,
    DocumentStyle,
    Image,
    Metadata,
    OfficeFormat,
    Paragraph,
    Shape,
    Slide,
    TextRun,
)

logger = logging.getLogger(__name__)

IWA_MAGIC = b"IWA1"
PROTOBUF_VARINT_MAX = 10
TITLE_MAX_WORDS = 12
TITLE_MAX_LENGTH = 140
DEFAULT_SLIDE_STYLE = DocumentStyle(font_family="Helvetica Neue", font_size=18.0)
TITLE_STYLE = DocumentStyle(font_family="Helvetica Neue", font_size=28.0, bold=True)

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".heic",
    ".webp",
    ".pdf",
    ".svg",
}
VIDEO_EXTENSIONS = {
    ".mov",
    ".mp4",
    ".m4v",
    ".avi",
    ".mkv",
    ".webm",
}
TRANSITION_KEYWORDS = (
    "dissolve",
    "fade",
    "move in",
    "move out",
    "push",
    "wipe",
    "cube",
    "flip",
    "revolve",
    "doorway",
    "anvil",
    "confetti",
    "sparkle",
    "magic move",
)
ANIMATION_KEYWORDS = (
    "build",
    "animate",
    "animation",
    "appear",
    "scale",
    "spin",
    "move",
    "action",
)
NOTE_PATTERNS = (
    re.compile(r"^(?:presenter|speaker)\s+notes?\s*:?\s*(.+)$", re.IGNORECASE),
    re.compile(r"^notes?\s*:?\s*(.+)$", re.IGNORECASE),
)
PRINTABLE_RUN_RE = re.compile(rb"[\x09\x0A\x0D\x20-\x7E]{4,}")
MEDIA_REF_RE = re.compile(
    r"(?:Data|Movies|Media|QuickLook|Resources)/[A-Za-z0-9._/\- ]+",
    re.IGNORECASE,
)
SLIDE_NUMBER_RE = re.compile(r"Slide-(\d+)", re.IGNORECASE)


@dataclass(slots=True)
class _AutomationSlide:
    """Slide data recovered via macOS Keynote automation."""

    index: int
    texts: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _SlideRecord:
    """Internal slide representation prior to conversion into public models."""

    index: int
    archive_path: str
    texts: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    image_refs: list[str] = field(default_factory=list)
    video_refs: list[str] = field(default_factory=list)
    layout_name: str | None = None
    master_slide: str | None = None
    transition_name: str | None = None
    transition_duration: float | None = None
    build_count: int = 0
    animation_names: list[str] = field(default_factory=list)


class _IWAParser:
    """Minimal parser for iWork Archive ``.iwa`` containers.

    Apple stores protobuf payloads in a sequence of varint-delimited chunks,
    optionally compressed with Snappy. This parser returns a list of raw
    protobuf payload bytes for downstream heuristic scanning.
    """

    def __init__(self, data: bytes):
        self._data = data
        self._position = 0

    def parse(self) -> list[bytes]:
        """Return protobuf payloads contained in the IWA stream."""
        if not self._data:
            return []

        if self._data.startswith(IWA_MAGIC):
            self._position = len(IWA_MAGIC)

        messages: list[bytes] = []
        while self._position < len(self._data):
            try:
                chunk_size = self._read_varint()
            except ValueError:
                break

            if chunk_size <= 0:
                break
            end = self._position + chunk_size
            if end > len(self._data):
                break

            chunk = self._data[self._position : end]
            self._position = end

            if SNAPPY_AVAILABLE:
                try:
                    messages.append(snappy.decompress(chunk))
                    continue
                except Exception:
                    logger.debug("Snappy decompression failed; keeping raw IWA chunk.")

            messages.append(chunk)

        return messages

    def _read_varint(self) -> int:
        result = 0
        shift = 0
        for _ in range(PROTOBUF_VARINT_MAX):
            if self._position >= len(self._data):
                raise ValueError("Unexpected end of varint stream")
            byte = self._data[self._position]
            self._position += 1
            result |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                return result
            shift += 7
        raise ValueError("Malformed protobuf varint")


class _ProtobufScanner:
    """Heuristic protobuf scanner for string-like and nested message content."""

    @classmethod
    def extract_strings(cls, data: bytes, *, max_depth: int = 3) -> list[str]:
        strings: list[str] = []
        cls._scan_message(data, strings, depth=0, max_depth=max_depth)
        strings.extend(cls._extract_printable_runs(data))
        return cls._dedupe(strings)

    @classmethod
    def _scan_message(
        cls,
        data: bytes,
        strings: list[str],
        *,
        depth: int,
        max_depth: int,
    ) -> None:
        position = 0
        while position < len(data):
            try:
                key, position = cls._read_varint(data, position)
            except ValueError:
                return

            wire_type = key & 0x7

            if wire_type == 0:
                try:
                    _, position = cls._read_varint(data, position)
                except ValueError:
                    return
                continue

            if wire_type == 1:
                position += 8
                continue

            if wire_type == 5:
                position += 4
                continue

            if wire_type != 2:
                return

            try:
                length, position = cls._read_varint(data, position)
            except ValueError:
                return

            segment = data[position : position + length]
            position += length
            if not segment:
                continue

            if cls._looks_like_text(segment):
                decoded = segment.decode("utf-8", errors="ignore").strip()
                if decoded:
                    strings.append(decoded)
                continue

            if depth < max_depth and len(segment) <= 16384:
                cls._scan_message(
                    segment, strings, depth=depth + 1, max_depth=max_depth
                )

    @staticmethod
    def _read_varint(data: bytes, position: int) -> tuple[int, int]:
        result = 0
        shift = 0
        for _ in range(PROTOBUF_VARINT_MAX):
            if position >= len(data):
                raise ValueError("Unexpected end of varint")
            byte = data[position]
            position += 1
            result |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                return result, position
            shift += 7
        raise ValueError("Invalid protobuf varint")

    @staticmethod
    def _looks_like_text(segment: bytes) -> bool:
        try:
            text = segment.decode("utf-8", errors="strict").strip()
        except UnicodeDecodeError:
            return False

        if len(text) < 2:
            return False
        printable_ratio = sum(
            1 for char in text if char.isprintable() or char.isspace()
        ) / max(
            len(text),
            1,
        )
        alpha_count = sum(1 for char in text if char.isalpha())
        return printable_ratio >= 0.9 and alpha_count >= 1

    @staticmethod
    def _extract_printable_runs(data: bytes) -> list[str]:
        results: list[str] = []
        for match in PRINTABLE_RUN_RE.finditer(data):
            text = match.group(0).decode("utf-8", errors="ignore").strip()
            if text:
                results.append(text)
        return results

    @staticmethod
    def _dedupe(values: Iterable[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped


class KeynoteProcessor:
    """Parse, inspect, and export Apple Keynote presentations."""

    def __init__(
        self,
        *,
        use_textutil_fallback: bool | None = None,
        use_keynote_automation: bool | None = None,
    ) -> None:
        self.is_macos = platform.system() == "Darwin"
        self.use_textutil_fallback = (
            self.is_macos if use_textutil_fallback is None else use_textutil_fallback
        )
        self.use_keynote_automation = (
            self.is_macos if use_keynote_automation is None else use_keynote_automation
        )
        self._source_path: Path | None = None
        self._document: DocumentContent | None = None
        self._slide_records: list[_SlideRecord] = []
        self._preview_image: bytes | None = None
        self._slide_thumbnails: list[bytes] = []

    def parse(self, path: Path) -> DocumentContent:
        """Parse a Keynote package and cache the extracted document."""
        source = self._validate_path(path)

        try:
            with zipfile.ZipFile(source, "r") as archive:
                metadata = self._extract_metadata_from_archive(archive, source)
                master_names = self._extract_master_slide_names(archive)
                slide_records = self._extract_slide_records(
                    archive, master_names=master_names
                )
                images = self._extract_image_assets(archive)
                preview_image = self._extract_preview_image(archive)
                thumbnails = self._extract_slide_thumbnail_images(archive)
                resource_bytes = self._build_resources(preview_image, thumbnails)

                if self.use_keynote_automation:
                    try:
                        automated = self._extract_text_with_keynote_automation(source)
                        self._merge_automation_slide_data(slide_records, automated)
                    except Exception as exc:  # pragma: no cover - platform dependent
                        logger.debug(
                            "Keynote automation text extraction failed: %s", exc
                        )

        except zipfile.BadZipFile as exc:
            raise InvalidDocumentStructureError(
                "Invalid Keynote package; expected a ZIP-based .key archive"
            ) from exc

        slides = [
            self._record_to_slide(record, images=images) for record in slide_records
        ]
        shapes = [shape for slide in slides for shape in slide.shapes]
        flattened_paragraphs = self._flatten_slide_paragraphs(slides)

        if not flattened_paragraphs and self.use_textutil_fallback and self.is_macos:
            fallback_text = self._extract_text_with_textutil(source)
            if fallback_text:
                flattened_paragraphs = self._paragraphs_from_lines(
                    fallback_text.splitlines()
                )

        embedded_video_paths = sorted(
            {ref for record in slide_records for ref in record.video_refs}
        )

        document = DocumentContent(
            format=OfficeFormat.KEYNOTE,
            paragraphs=flattened_paragraphs,
            images=images,
            shapes=shapes,
            slides=slides,
            metadata=metadata,
            styles={
                "title": TITLE_STYLE,
                "slide-body": DEFAULT_SLIDE_STYLE,
            },
            document_properties={
                "slide_count": len(slides),
                "image_count": len(images),
                "shape_count": len(shapes),
                "master_slide_count": len(master_names),
                "has_builds": any(record.build_count for record in slide_records),
                "has_transitions": any(
                    record.transition_name for record in slide_records
                ),
                "embedded_video_count": len(embedded_video_paths),
                "embedded_video_paths": "\n".join(embedded_video_paths),
                "thumbnail_count": len(thumbnails),
                "snappy_available": SNAPPY_AVAILABLE,
            },
            resources=resource_bytes,
        )

        self._source_path = source
        self._document = document
        self._slide_records = slide_records
        self._preview_image = preview_image
        self._slide_thumbnails = thumbnails
        return document

    def get_slide_count(self) -> int:
        """Return the number of slides in the parsed presentation."""
        self._ensure_parsed()
        return len(self._document.slides)

    def extract_slide(self, index: int) -> Slide:
        """Return an individual slide using zero-based indexing."""
        self._ensure_parsed()
        if index < 0 or index >= len(self._document.slides):
            raise InvalidDocumentStructureError(
                f"Slide index out of range: {index}",
                element_id=f"slide-{index}",
            )
        return self._document.slides[index]

    def extract_all_slides(self) -> list[Slide]:
        """Return all parsed slides."""
        self._ensure_parsed()
        return list(self._document.slides)

    def extract_text(self) -> str:
        """Return flattened text across all slides."""
        self._ensure_parsed()
        slide_texts: list[str] = []
        for slide in self._document.slides:
            parts: list[str] = []
            if slide.title:
                parts.append(self._paragraph_text(slide.title))
            parts.extend(self._paragraph_text(paragraph) for paragraph in slide.body)
            text = "\n".join(part for part in parts if part.strip())
            if text.strip():
                slide_texts.append(text)
        return "\n\n".join(slide_texts)

    def extract_speaker_notes(self) -> list[str]:
        """Return presenter notes for every slide."""
        self._ensure_parsed()
        notes: list[str] = []
        for slide in self._document.slides:
            slide_notes = "\n".join(
                self._paragraph_text(paragraph)
                for paragraph in slide.notes
                if self._paragraph_text(paragraph).strip()
            ).strip()
            notes.append(slide_notes)
        return notes

    def extract_images(self) -> list[Image]:
        """Return all embedded raster and vector image assets."""
        self._ensure_parsed()
        return list(self._document.images)

    def extract_shapes(self) -> list[Shape]:
        """Return all synthesized slide shapes."""
        self._ensure_parsed()
        return list(self._document.shapes)

    def extract_metadata(self) -> Metadata:
        """Return parsed presentation metadata."""
        self._ensure_parsed()
        return self._document.metadata

    def get_preview_image(self) -> bytes:
        """Return the package preview image if present."""
        self._ensure_parsed()
        return self._preview_image or b""

    def get_slide_thumbnails(self) -> list[bytes]:
        """Return packaged slide thumbnail images when available."""
        self._ensure_parsed()
        return list(self._slide_thumbnails)

    def to_pdf(self, output_path: Path) -> Path:
        """Export the presentation to PDF via Keynote automation on macOS."""
        self._ensure_parsed()
        source = self._source_path
        if source is None:
            raise DocumentValidationError("Keynote source path is not available")

        resolved_output = Path(output_path).expanduser().resolve()
        resolved_output.parent.mkdir(parents=True, exist_ok=True)

        if not self.is_macos:
            raise DocumentValidationError("Keynote PDF export requires macOS")

        last_error: Exception | None = None

        if self.use_keynote_automation:
            try:
                return self._export_pdf_with_keynote(source, resolved_output)
            except Exception as exc:  # pragma: no cover - platform dependent
                last_error = exc
                logger.debug("Keynote PDF automation failed: %s", exc)

        if self.use_textutil_fallback:
            try:
                if self._export_pdf_with_textutil(source, resolved_output):
                    return resolved_output
            except Exception as exc:  # pragma: no cover - platform dependent
                last_error = exc
                logger.debug("textutil PDF fallback failed: %s", exc)

        if last_error is not None:
            raise InvalidDocumentStructureError(
                f"Unable to export Keynote presentation to PDF: {last_error}"
            ) from last_error
        raise InvalidDocumentStructureError(
            "Unable to export Keynote presentation to PDF"
        )

    def _ensure_parsed(self) -> None:
        if self._document is None:
            raise DocumentValidationError(
                "Call parse(path) before accessing presentation data"
            )

    def _validate_path(self, path: Path) -> Path:
        source = Path(path).expanduser().resolve()
        if not source.exists():
            raise DocumentValidationError("Keynote file not found", details=str(source))
        if not source.is_file():
            raise DocumentValidationError(
                "Keynote path is not a file", details=str(source)
            )
        if source.suffix.lower() not in {".key", ".keynote"}:
            raise DocumentValidationError(
                "Unsupported file extension for Keynote processor",
                details=source.suffix or "<none>",
            )
        if not zipfile.is_zipfile(source):
            raise DocumentValidationError(
                "Expected a ZIP-based Keynote package", details=str(source)
            )
        return source

    def _extract_slide_records(
        self,
        archive: zipfile.ZipFile,
        *,
        master_names: list[str],
    ) -> list[_SlideRecord]:
        slide_paths = [
            name
            for name in archive.namelist()
            if name.startswith("Index/")
            and name.endswith(".iwa")
            and "Slide-" in Path(name).name
        ]
        slide_paths.sort(key=self._natural_sort_key)

        records: list[_SlideRecord] = []
        for slide_index, slide_path in enumerate(slide_paths, start=1):
            raw_data = archive.read(slide_path)
            messages = _IWAParser(raw_data).parse() or [raw_data]
            texts: list[str] = []
            image_refs: list[str] = []
            video_refs: list[str] = []
            transition_name: str | None = None
            transition_duration: float | None = None
            build_count = 0
            animation_names: list[str] = []
            layout_name: str | None = None

            for message in messages:
                message_strings = _ProtobufScanner.extract_strings(message)
                texts.extend(message_strings)
                refs = self._extract_media_refs(message)
                image_refs.extend(refs["images"])
                video_refs.extend(refs["videos"])

                transition_candidate, duration_candidate, builds, animations = (
                    self._extract_transition_build_metadata(message_strings)
                )
                if transition_candidate and not transition_name:
                    transition_name = transition_candidate
                if duration_candidate is not None and transition_duration is None:
                    transition_duration = duration_candidate
                build_count += builds
                animation_names.extend(animations)

                if layout_name is None:
                    layout_name = self._extract_layout_name(message_strings)

            cleaned_texts = self._clean_text_values(texts)
            notes = self._extract_note_values(cleaned_texts)
            body_texts = [value for value in cleaned_texts if value not in set(notes)]
            if layout_name is None and master_names:
                layout_name = master_names[min(slide_index - 1, len(master_names) - 1)]

            records.append(
                _SlideRecord(
                    index=slide_index,
                    archive_path=slide_path,
                    texts=body_texts,
                    notes=notes,
                    image_refs=self._dedupe_paths(image_refs),
                    video_refs=self._dedupe_paths(video_refs),
                    layout_name=layout_name,
                    master_slide=layout_name,
                    transition_name=transition_name,
                    transition_duration=transition_duration,
                    build_count=build_count,
                    animation_names=self._dedupe_strings(animation_names),
                )
            )

        if not records:
            raise InvalidDocumentStructureError(
                "No slide archives found in Keynote package"
            )
        return records

    def _extract_master_slide_names(self, archive: zipfile.ZipFile) -> list[str]:
        master_paths = [
            name
            for name in archive.namelist()
            if name.startswith("Index/")
            and name.endswith(".iwa")
            and "Master" in Path(name).name
        ]
        master_paths.sort(key=self._natural_sort_key)

        names: list[str] = []
        for master_path in master_paths:
            raw_data = archive.read(master_path)
            messages = _IWAParser(raw_data).parse() or [raw_data]
            strings: list[str] = []
            for message in messages:
                strings.extend(_ProtobufScanner.extract_strings(message))
            cleaned = self._clean_text_values(strings)
            candidates = [
                value
                for value in cleaned
                if any(
                    token in value.lower()
                    for token in ("title", "photo", "master", "layout")
                )
                or len(value.split()) <= 6
            ]
            if candidates:
                names.append(candidates[0])
            else:
                names.append(Path(master_path).stem.replace("-", " "))
        return self._dedupe_strings(names)

    def _record_to_slide(self, record: _SlideRecord, *, images: list[Image]) -> Slide:
        title_text, body_texts = self._split_title_and_body(record.texts)
        title = self._make_paragraph(title_text, title=True) if title_text else None
        body = [self._make_paragraph(text) for text in body_texts]
        notes = [self._make_paragraph(text) for text in record.notes]
        slide_images = self._match_images_to_slide(record, images)
        slide_shapes = self._build_slide_shapes(record, title_text, body_texts)

        transition: dict[str, str | float] | None = None
        if (
            record.transition_name
            or record.transition_duration is not None
            or record.build_count
        ):
            transition = {}
            if record.transition_name:
                transition["name"] = record.transition_name
            if record.transition_duration is not None:
                transition["duration"] = record.transition_duration
            if record.build_count:
                transition["builds"] = str(record.build_count)
            if record.animation_names:
                transition["animations"] = ", ".join(record.animation_names)

        return Slide(
            title=title,
            body=body,
            notes=notes,
            images=slide_images,
            shapes=slide_shapes,
            layout_name=record.layout_name,
            transition=transition,
        )

    def _build_slide_shapes(
        self,
        record: _SlideRecord,
        title_text: str | None,
        body_texts: list[str],
    ) -> list[Shape]:
        shapes: list[Shape] = []
        if title_text:
            shapes.append(
                Shape(
                    shape_type="title",
                    path=[],
                    text=self._make_paragraph(title_text, title=True),
                    style=TITLE_STYLE,
                    properties={
                        "slide_index": str(record.index),
                        "archive_path": record.archive_path,
                    },
                )
            )

        for body_index, text in enumerate(body_texts, start=1):
            shapes.append(
                Shape(
                    shape_type="text-box",
                    path=[],
                    text=self._make_paragraph(text),
                    style=DEFAULT_SLIDE_STYLE,
                    properties={
                        "slide_index": str(record.index),
                        "archive_path": record.archive_path,
                        "text_index": str(body_index),
                    },
                )
            )

        for video_ref in record.video_refs:
            shapes.append(
                Shape(
                    shape_type="video",
                    path=[],
                    style=DEFAULT_SLIDE_STYLE,
                    properties={
                        "slide_index": str(record.index),
                        "internal_path": video_ref,
                    },
                )
            )

        if record.build_count and shapes:
            shapes[0].properties["build_count"] = str(record.build_count)
        if record.animation_names and shapes:
            shapes[0].properties["animations"] = ", ".join(record.animation_names)
        return shapes

    def _extract_image_assets(self, archive: zipfile.ZipFile) -> list[Image]:
        images: list[Image] = []
        for name in archive.namelist():
            path = Path(name)
            if (
                not name.startswith("Data/")
                or path.suffix.lower() not in IMAGE_EXTENSIONS
            ):
                continue

            mime_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
            images.append(
                Image(
                    data=archive.read(name),
                    mime_type=mime_type,
                    title=path.name,
                    description=f"Embedded Keynote asset: {path.name}",
                    properties={
                        "internal_path": name,
                        "extension": path.suffix.lower(),
                    },
                )
            )
        return images

    def _extract_metadata_from_archive(
        self, archive: zipfile.ZipFile, source: Path
    ) -> Metadata:
        metadata = Metadata(
            title=source.stem,
            modified_at=datetime.fromtimestamp(source.stat().st_mtime, tz=UTC),
        )

        for name in archive.namelist():
            if not name.lower().endswith(".plist"):
                continue
            try:
                plist_data = plistlib.loads(archive.read(name))
            except Exception:
                logger.debug("Failed to parse plist metadata from %s", name)
                continue
            self._apply_plist_metadata(metadata, plist_data, origin=name)

        if "Index/Document.iwa" in archive.namelist():
            try:
                document_strings = _ProtobufScanner.extract_strings(
                    archive.read("Index/Document.iwa")
                )
                inferred_title = self._extract_document_title(document_strings)
                if inferred_title and (
                    metadata.title is None or metadata.title == source.stem
                ):
                    metadata.title = inferred_title
            except Exception:
                logger.debug("Failed to infer metadata from Index/Document.iwa")

        return metadata

    def _apply_plist_metadata(
        self, metadata: Metadata, value: Any, *, origin: str
    ) -> None:
        flattened = self._flatten_plist(value)
        for key, item in flattened.items():
            normalized = key.lower()
            if metadata.title is None and normalized.endswith(
                ("title", "documenttitle")
            ):
                metadata.title = str(item)
            elif metadata.author is None and normalized.endswith(("author", "creator")):
                metadata.author = str(item)
            elif metadata.subject is None and normalized.endswith(
                ("subject", "description")
            ):
                metadata.subject = str(item)
            elif normalized.endswith("company") and metadata.company is None:
                metadata.company = str(item)
            elif normalized.endswith(("keyword", "keywords")):
                if isinstance(item, str):
                    metadata.keywords.extend(
                        keyword.strip()
                        for keyword in re.split(r"[;,]", item)
                        if keyword.strip()
                    )
            elif (
                normalized.endswith(("created", "creationdate"))
                and metadata.created_at is None
            ):
                converted = self._coerce_datetime(item)
                if converted:
                    metadata.created_at = converted
            elif (
                normalized.endswith(("modified", "modificationdate"))
                and metadata.modified_at is None
            ):
                converted = self._coerce_datetime(item)
                if converted:
                    metadata.modified_at = converted

            scalar = self._coerce_scalar(item)
            if scalar is not None:
                metadata.custom_properties[f"{origin}:{key}"] = scalar

        metadata.keywords = self._dedupe_strings(metadata.keywords)

    def _extract_preview_image(self, archive: zipfile.ZipFile) -> bytes | None:
        for candidate in ("preview.jpg", "preview.jpeg", "QuickLook/Preview.jpg"):
            if candidate in archive.namelist():
                return archive.read(candidate)

        preview_names = [
            name
            for name in archive.namelist()
            if "preview" in name.lower()
            and Path(name).suffix.lower() in {".jpg", ".jpeg", ".png"}
        ]
        preview_names.sort(key=self._natural_sort_key)
        return archive.read(preview_names[0]) if preview_names else None

    def _extract_slide_thumbnail_images(self, archive: zipfile.ZipFile) -> list[bytes]:
        thumbnail_names = [
            name
            for name in archive.namelist()
            if Path(name).suffix.lower() in {".jpg", ".jpeg", ".png"}
            and (
                "thumbnail" in name.lower()
                or "preview-micro" in name.lower()
                or "slidepreview" in name.lower()
            )
        ]
        thumbnail_names.sort(key=self._natural_sort_key)
        return [archive.read(name) for name in thumbnail_names]

    def _build_resources(
        self,
        preview_image: bytes | None,
        thumbnails: list[bytes],
    ) -> dict[str, bytes]:
        resources: dict[str, bytes] = {}
        if preview_image is not None:
            resources["preview.jpg"] = preview_image
        for index, thumbnail in enumerate(thumbnails, start=1):
            resources[f"thumbnail-{index}.jpg"] = thumbnail
        return resources

    def _extract_media_refs(self, data: bytes) -> dict[str, list[str]]:
        strings = _ProtobufScanner.extract_strings(data)
        refs: list[str] = []
        for value in strings:
            refs.extend(MEDIA_REF_RE.findall(value))

        images = [ref for ref in refs if Path(ref).suffix.lower() in IMAGE_EXTENSIONS]
        videos = [ref for ref in refs if Path(ref).suffix.lower() in VIDEO_EXTENSIONS]
        return {
            "images": self._dedupe_paths(images),
            "videos": self._dedupe_paths(videos),
        }

    def _extract_transition_build_metadata(
        self,
        strings: list[str],
    ) -> tuple[str | None, float | None, int, list[str]]:
        transition_name: str | None = None
        duration: float | None = None
        build_count = 0
        animations: list[str] = []

        for value in strings:
            lowered = value.lower()
            if transition_name is None:
                for keyword in TRANSITION_KEYWORDS:
                    if keyword in lowered:
                        transition_name = keyword.title()
                        break

            if any(keyword in lowered for keyword in ANIMATION_KEYWORDS):
                build_count += 1
                animations.append(value.strip())

            if duration is None:
                duration_match = re.search(
                    r"(\d+(?:\.\d+)?)\s*(?:sec|secs|second|seconds|s)\b", lowered
                )
                if duration_match:
                    duration = float(duration_match.group(1))

        return transition_name, duration, build_count, self._dedupe_strings(animations)

    def _extract_layout_name(self, strings: list[str]) -> str | None:
        for value in strings:
            lowered = value.lower()
            if any(
                token in lowered
                for token in ("layout", "master", "title &", "photo", "bullet")
            ):
                return value
        return None

    def _extract_note_values(self, values: list[str]) -> list[str]:
        notes: list[str] = []
        for value in values:
            for pattern in NOTE_PATTERNS:
                match = pattern.match(value)
                if match:
                    note = match.group(1).strip()
                    if note:
                        notes.append(note)
                    break
        return self._dedupe_strings(notes)

    def _split_title_and_body(self, texts: list[str]) -> tuple[str | None, list[str]]:
        title: str | None = None
        body: list[str] = []
        for text in texts:
            if title is None and self._looks_like_title(text):
                title = text
            else:
                body.append(text)
        if title is None and body:
            title = body[0]
            body = body[1:]
        return title, body

    def _looks_like_title(self, value: str) -> bool:
        stripped = value.strip()
        if not stripped:
            return False
        if len(stripped) > TITLE_MAX_LENGTH:
            return False
        if len(stripped.split()) > TITLE_MAX_WORDS:
            return False
        if stripped.endswith((".png", ".jpg", ".mov", ".mp4")):
            return False
        return any(char.isalpha() for char in stripped)

    def _make_paragraph(self, text: str, *, title: bool = False) -> Paragraph:
        style = TITLE_STYLE if title else DEFAULT_SLIDE_STYLE
        return Paragraph(
            runs=[TextRun(text=text, style=style)],
            style=style,
            is_heading=title,
            heading_level=1 if title else None,
        )

    def _flatten_slide_paragraphs(self, slides: list[Slide]) -> list[Paragraph]:
        paragraphs: list[Paragraph] = []
        for slide in slides:
            if slide.title:
                paragraphs.append(slide.title)
            paragraphs.extend(slide.body)
        return paragraphs

    def _paragraphs_from_lines(self, lines: Iterable[str]) -> list[Paragraph]:
        return [self._make_paragraph(line.strip()) for line in lines if line.strip()]

    def _paragraph_text(self, paragraph: Paragraph) -> str:
        return "".join(run.text for run in paragraph.runs)

    def _match_images_to_slide(
        self, record: _SlideRecord, images: list[Image]
    ) -> list[Image]:
        if not record.image_refs:
            return []

        matched: list[Image] = []
        for image in images:
            internal_path = str(image.properties.get("internal_path", ""))
            if any(
                ref == internal_path or Path(ref).name == Path(internal_path).name
                for ref in record.image_refs
            ):
                matched.append(image)
        return matched

    def _extract_document_title(self, strings: list[str]) -> str | None:
        cleaned = self._clean_text_values(strings)
        if cleaned:
            return cleaned[0]
        return None

    def _clean_text_values(self, values: Iterable[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            for line in value.splitlines():
                candidate = line.strip()
                if self._should_keep_text(candidate):
                    cleaned.append(candidate)
        return self._dedupe_strings(cleaned)

    def _should_keep_text(self, value: str) -> bool:
        if len(value) < 2:
            return False
        if value.lower().startswith(("index/", "data/", "movies/", "media/")):
            return False
        if MEDIA_REF_RE.fullmatch(value):
            return False
        if value.startswith("Slide-") and value.endswith(".iwa"):
            return False
        if not any(char.isalpha() for char in value):
            return False
        noise_ratio = sum(
            1 for char in value if char.isalnum() or char.isspace()
        ) / max(len(value), 1)
        return not noise_ratio < 0.6

    def _merge_automation_slide_data(
        self,
        records: list[_SlideRecord],
        automated_slides: list[_AutomationSlide],
    ) -> None:
        by_index = {slide.index: slide for slide in automated_slides}
        for record in records:
            automated = by_index.get(record.index)
            if automated is None:
                continue

            merged_texts = self._dedupe_strings(record.texts + automated.texts)
            merged_notes = self._dedupe_strings(record.notes + automated.notes)
            record.texts = merged_texts
            record.notes = merged_notes

    def _extract_text_with_textutil(self, path: Path) -> str:
        if not self.is_macos or shutil.which("textutil") is None:
            return ""
        result = subprocess.run(
            ["textutil", "-convert", "txt", "-stdout", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    def _extract_text_with_keynote_automation(
        self,
        path: Path,
    ) -> list[_AutomationSlide]:
        if not self.is_macos or shutil.which("osascript") is None:
            return []

        record_separator = "<<<AGENTIC_BRAIN_SLIDE>>>"
        field_separator = "<<<AGENTIC_BRAIN_FIELD>>>"
        escaped_path = self._escape_applescript_string(str(path))
        applescript = f"""
        on join_list(theList, theDelimiter)
            set oldDelims to AppleScript's text item delimiters
            set AppleScript's text item delimiters to theDelimiter
            set joined to theList as string
            set AppleScript's text item delimiters to oldDelims
            return joined
        end join_list

        tell application "Keynote"
            set docRef to open POSIX file "{escaped_path}"
            delay 1
            set outputRecords to {{}}
            repeat with slideIndex from 1 to count of slides of docRef
                set thisSlide to slide slideIndex of docRef
                set slideTexts to {{}}
                try
                    repeat with thisTextItem in text items of thisSlide
                        try
                            set end of slideTexts to (object text of thisTextItem as string)
                        end try
                    end repeat
                end try
                set noteText to ""
                try
                    set noteText to (presenter notes of thisSlide as string)
                end try
                set recordText to (slideIndex as string) & "{field_separator}" & my join_list(slideTexts, linefeed) & "{field_separator}" & noteText
                set end of outputRecords to recordText
            end repeat
            close docRef saving no
            return my join_list(outputRecords, "{record_separator}")
        end tell
        """

        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            raise DocumentValidationError(
                "Keynote automation text extraction failed",
                details=result.stderr.strip() or result.stdout.strip(),
            )

        slides: list[_AutomationSlide] = []
        for record_text in result.stdout.split(record_separator):
            record_text = record_text.strip()
            if not record_text:
                continue
            parts = record_text.split(field_separator)
            if len(parts) != 3:
                continue
            index = int(parts[0].strip())
            texts = self._clean_text_values(parts[1].splitlines())
            notes = self._clean_text_values(parts[2].splitlines())
            slides.append(_AutomationSlide(index=index, texts=texts, notes=notes))
        return slides

    def _export_pdf_with_keynote(self, source: Path, output_path: Path) -> Path:
        if shutil.which("osascript") is None:
            raise DocumentValidationError(
                "osascript is not available for Keynote automation"
            )

        escaped_input = self._escape_applescript_string(str(source))
        escaped_output = self._escape_applescript_string(str(output_path))
        applescript = f"""
        tell application "Keynote"
            set docRef to open POSIX file "{escaped_input}"
            delay 1
            export docRef to POSIX file "{escaped_output}" as PDF with properties {{slide numbers:false, skipped slides:true, PDF image quality:"best"}}
            close docRef saving no
        end tell
        """
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if result.returncode != 0:
            raise InvalidDocumentStructureError(
                "Keynote automation export failed",
                element_id=result.stderr.strip()
                or result.stdout.strip()
                or "osascript",
            )
        if not output_path.exists():
            raise InvalidDocumentStructureError(
                "Keynote export finished without creating a PDF"
            )
        return output_path

    def _export_pdf_with_textutil(self, source: Path, output_path: Path) -> bool:
        if shutil.which("textutil") is None:
            return False
        result = subprocess.run(
            ["textutil", "-convert", "pdf", "-output", str(output_path), str(source)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return result.returncode == 0 and output_path.exists()

    def _flatten_plist(self, value: Any, prefix: str = "") -> dict[str, Any]:
        flattened: dict[str, Any] = {}
        if isinstance(value, dict):
            for key, item in value.items():
                child_prefix = f"{prefix}.{key}" if prefix else str(key)
                flattened.update(self._flatten_plist(item, prefix=child_prefix))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                child_prefix = f"{prefix}[{index}]"
                flattened.update(self._flatten_plist(item, prefix=child_prefix))
        else:
            flattened[prefix or "value"] = value
        return flattened

    def _coerce_datetime(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        if isinstance(value, str):
            for parser in (datetime.fromisoformat,):
                try:
                    parsed = parser(value)
                    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
                except ValueError:
                    continue
        return None

    def _coerce_scalar(self, value: Any) -> str | int | float | bool | datetime | None:
        if isinstance(value, (str, int, float, bool, datetime)):
            return value
        return None

    def _escape_applescript_string(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _dedupe_strings(self, values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for value in values:
            candidate = value.strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            deduped.append(candidate)
        return deduped

    def _dedupe_paths(self, values: Iterable[str]) -> list[str]:
        normalized = [value.strip() for value in values if value.strip()]
        return self._dedupe_strings(normalized)

    def _natural_sort_key(self, value: str) -> tuple[Any, ...]:
        parts = re.split(r"(\d+)", value)
        return tuple(int(part) if part.isdigit() else part.lower() for part in parts)


__all__ = ["KeynoteProcessor"]
