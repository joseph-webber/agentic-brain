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

"""Office security integration that wraps Phase 2 primitives for OOXML files."""

from __future__ import annotations

import hashlib
import logging
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Iterable, Sequence
from xml.etree import ElementTree as ET

try:  # pragma: no cover - optional strong encryption
    import pyzipper

    PYZIPPER_AVAILABLE = True
except ImportError:  # pragma: no cover
    pyzipper = None
    PYZIPPER_AVAILABLE = False

from ..security import (
    AuditEntry,
    AuditLog,
    PIIDetector,
    PIIEntity,
    PIIType,
    RedactionStyle,
)
from .models import Metadata

LOGGER = logging.getLogger(__name__)


class OfficeDocumentKind(StrEnum):
    """Supported OOXML package types."""

    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"


@dataclass(slots=True)
class OfficePIIMatch:
    """PII finding with Office-specific provenance."""

    entity: PIIEntity
    source: str
    context: str

    def to_dict(self) -> dict[str, str]:
        """Serialize match for reporting."""
        return {
            "entity_type": self.entity.entity_type,
            "text": self.entity.text,
            "confidence": f"{self.entity.score:.2f}",
            "source": self.source,
            "context": self.context,
        }


@dataclass(slots=True)
class MacroFinding:
    part: str
    description: str
    severity: str = "high"


@dataclass(slots=True)
class MacroCheckResult:
    document: Path
    findings: list[MacroFinding] = field(default_factory=list)
    macros_removed: bool = False
    output_path: Path | None = None

    @property
    def has_macros(self) -> bool:
        return bool(self.findings)


@dataclass(slots=True)
class ExternalLink:
    relationship_id: str
    target: str
    source_part: str
    target_mode: str


@dataclass(slots=True)
class ExternalLinkReport:
    document: Path
    links: list[ExternalLink] = field(default_factory=list)


@dataclass(slots=True)
class MetadataSanitizationReport:
    input_path: Path
    output_path: Path
    original_metadata: Metadata
    removed_fields: dict[str, str]


@dataclass(slots=True)
class EncryptionResult:
    input_path: Path
    output_path: Path
    algorithm: str
    strength_bits: int
    encrypted: bool


class OfficeSecurityService:
    """High-level Office security orchestrator built on Phase 2 components."""

    _REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
    _CORE_NS = {
        "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
        "dc": "http://purl.org/dc/elements/1.1/",
        "dcterms": "http://purl.org/dc/terms/",
    }

    def __init__(
        self,
        confidence_threshold: float = 0.7,
        redaction_style: RedactionStyle = RedactionStyle.BLACK_BOX,
        audit_log: AuditLog | None = None,
        detector: PIIDetector | None = None,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.redaction_style = redaction_style
        self.detector = detector or PIIDetector(
            confidence_threshold=confidence_threshold
        )
        self.audit_log = audit_log or AuditLog()

    def scan_for_pii(
        self,
        path: str | Path,
        pii_types: Sequence[str | PIIType] | None = None,
    ) -> list[OfficePIIMatch]:
        document = Path(path)
        kind = self._detect_kind(document)
        allowed = self._normalise_pii_types(pii_types)
        matches: list[OfficePIIMatch] = []

        for source, text in self._extract_text_segments(document, kind).items():
            for entity in self.detector.scan_text(text):
                if allowed and entity.entity_type.lower() not in allowed:
                    continue
                context = text[max(entity.start - 60, 0) : entity.end + 60]
                matches.append(
                    OfficePIIMatch(
                        entity=entity,
                        source=source,
                        context=context,
                    )
                )

        self._log_event(document, "scan_pii", {"matches": len(matches)})
        return matches

    def redact_document(
        self,
        input_path: str | Path,
        output_path: str | Path | None = None,
        pii_types: Sequence[str | PIIType] | None = None,
    ) -> dict[str, int]:
        source = Path(input_path)
        destination = Path(
            output_path or source.with_name(f"{source.stem}.redacted{source.suffix}")
        )
        matches = self.scan_for_pii(source, pii_types)

        replacements = {
            match.entity.text: f"[REDACTED-{match.entity.entity_type.upper()}]"
            for match in matches
        }

        with zipfile.ZipFile(source, "r") as archive:
            with zipfile.ZipFile(
                destination, "w", compression=zipfile.ZIP_DEFLATED
            ) as target:
                for entry in archive.infolist():
                    data = archive.read(entry.filename)
                    if entry.filename.endswith(".xml") and replacements:
                        text = data.decode("utf-8", errors="ignore")
                        for needle, repl in replacements.items():
                            if needle in text:
                                text = text.replace(needle, repl)
                        data = text.encode("utf-8")
                    target.writestr(entry, data)

        self._log_event(
            source,
            "redact_document",
            {"output": str(destination), "pii_redacted": len(matches)},
        )
        return {"pii_redacted": len(matches), "output_path": str(destination)}

    def check_macros(
        self,
        path: str | Path,
        *,
        remove: bool = False,
        output_path: str | Path | None = None,
    ) -> MacroCheckResult:
        document = Path(path)
        findings: list[MacroFinding] = []

        with zipfile.ZipFile(document, "r") as archive:
            macro_parts = [
                name
                for name in archive.namelist()
                if "vbaProject.bin" in name.lower()
                or name.lower().endswith(".bin")
                and "vba" in name.lower()
            ]

            for part in macro_parts:
                findings.append(
                    MacroFinding(part=part, description="Embedded VBA project")
                )

            if remove and macro_parts:
                destination = Path(
                    output_path
                    or document.with_name(f"{document.stem}.nomacro{document.suffix}")
                )
                with zipfile.ZipFile(
                    destination, "w", compression=zipfile.ZIP_DEFLATED
                ) as target:
                    for entry in archive.infolist():
                        if entry.filename in macro_parts:
                            continue
                        target.writestr(entry, archive.read(entry.filename))
            else:
                destination = None

        self._log_event(
            document,
            "check_macros",
            {
                "macros_found": len(findings),
                "macros_removed": bool(remove and findings),
            },
        )

        return MacroCheckResult(
            document=document,
            findings=findings,
            macros_removed=bool(remove and findings),
            output_path=destination,
        )

    def check_external_links(self, path: str | Path) -> ExternalLinkReport:
        document = Path(path)
        links: list[ExternalLink] = []

        with zipfile.ZipFile(document, "r") as archive:
            for name in archive.namelist():
                if not name.endswith(".rels"):
                    continue
                try:
                    root = ET.fromstring(archive.read(name))
                except ET.ParseError:
                    continue
                for rel in root.findall("rel:Relationship", self._REL_NS):
                    mode = rel.get("TargetMode", "")
                    target = rel.get("Target", "")
                    if mode.lower() != "external":
                        continue
                    links.append(
                        ExternalLink(
                            relationship_id=rel.get("Id", ""),
                            target=target,
                            source_part=name,
                            target_mode=mode or "External",
                        )
                    )

        self._log_event(document, "check_external_links", {"links": len(links)})
        return ExternalLinkReport(document=document, links=links)

    def sanitize_metadata(
        self,
        path: str | Path,
        output_path: str | Path | None = None,
        *,
        remove_custom_properties: bool = True,
    ) -> MetadataSanitizationReport:
        document = Path(path)
        destination = Path(
            output_path or document.with_name(f"{document.stem}.clean{document.suffix}")
        )
        metadata = self._read_metadata(document)
        removed: dict[str, str] = {}

        with zipfile.ZipFile(document, "r") as archive:
            with zipfile.ZipFile(
                destination, "w", compression=zipfile.ZIP_DEFLATED
            ) as target:
                for entry in archive.infolist():
                    data = archive.read(entry.filename)

                    if entry.filename == "docProps/core.xml":
                        root = ET.fromstring(data)
                        for tag in (
                            "dc:creator",
                            "cp:lastModifiedBy",
                            "dc:title",
                            "dc:subject",
                            "cp:keywords",
                        ):
                            elem = root.find(tag, self._CORE_NS)
                            if elem is not None and elem.text:
                                removed[tag] = elem.text
                                elem.text = ""
                        data = ET.tostring(root, encoding="utf-8", xml_declaration=True)

                    elif entry.filename == "docProps/app.xml":
                        root = ET.fromstring(data)
                        ns = {
                            "ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
                        }
                        for tag in ("ep:Company", "ep:Manager"):
                            elem = root.find(tag, ns)
                            if elem is not None and elem.text:
                                removed[tag] = elem.text
                                elem.text = ""
                        data = ET.tostring(root, encoding="utf-8", xml_declaration=True)

                    elif (
                        remove_custom_properties
                        and entry.filename == "docProps/custom.xml"
                    ):
                        continue

                    target.writestr(entry, data)

        self._log_event(
            document,
            "sanitize_metadata",
            {"removed_fields": list(removed.keys()), "output": str(destination)},
        )
        return MetadataSanitizationReport(
            input_path=document,
            output_path=destination,
            original_metadata=metadata,
            removed_fields=removed,
        )

    def encrypt_document(
        self,
        path: str | Path,
        password: str,
        output_path: str | Path | None = None,
        *,
        strength_bits: int = 256,
    ) -> EncryptionResult:
        """Wrap the OOXML package in an AES-encrypted container."""
        if not PYZIPPER_AVAILABLE:  # pragma: no cover - dependency guard
            raise RuntimeError(
                "pyzipper is required for encrypt_document(). Install 'pyzipper>=0.3'."
            )

        document = Path(path)
        destination = Path(
            output_path or document.with_suffix(f"{document.suffix}.aes")
        )

        with zipfile.ZipFile(document, "r") as archive:
            with pyzipper.AESZipFile(
                destination,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                encryption=pyzipper.WZ_AES,
            ) as encrypted:
                encrypted.setpassword(password.encode("utf-8"))
                encrypted.setencryption(pyzipper.WZ_AES, nbits=strength_bits)
                for entry in archive.infolist():
                    encrypted.writestr(entry, archive.read(entry.filename))

        self._log_event(
            document,
            "encrypt_document",
            {
                "output": str(destination),
                "algorithm": "zip-aes",
                "strength": strength_bits,
            },
        )
        return EncryptionResult(
            input_path=document,
            output_path=destination,
            algorithm="zip-aes",
            strength_bits=strength_bits,
            encrypted=True,
        )

    def generate_audit_trail(
        self,
        path: str | Path,
        actions: Iterable[str] | None = None,
    ) -> list[AuditEntry]:
        """
        Return the audit trail for the provided document.

        Args:
            path: Document path.
            actions: Optional list of action names to filter.
        """

        document = Path(path)
        document_id = self._document_id(document)
        entries = self.audit_log.get_history(document_id=document_id)

        if actions:
            allowed = {action.lower() for action in actions}
            entries = [entry for entry in entries if entry.action.lower() in allowed]

        return entries

    def _detect_kind(self, path: Path) -> OfficeDocumentKind:
        suffix = path.suffix.lower().lstrip(".")
        try:
            return OfficeDocumentKind(suffix)
        except ValueError as exc:
            raise ValueError(f"Unsupported Office format: {path}") from exc

    def _extract_text_segments(
        self,
        path: Path,
        kind: OfficeDocumentKind,
    ) -> dict[str, str]:
        segments: dict[str, str] = {}

        with zipfile.ZipFile(path, "r") as archive:
            if kind == OfficeDocumentKind.DOCX:
                targets = ["word/document.xml"]
                targets += [
                    name
                    for name in archive.namelist()
                    if name.startswith("word/header")
                ]
                targets += [
                    name
                    for name in archive.namelist()
                    if name.startswith("word/footer")
                ]
                targets += [
                    name
                    for name in archive.namelist()
                    if name.startswith("word/comments")
                ]

            elif kind == OfficeDocumentKind.XLSX:
                targets = [
                    name
                    for name in archive.namelist()
                    if name.startswith("xl/worksheets/sheet")
                ]
                shared = "xl/sharedStrings.xml"
                if shared in archive.namelist():
                    targets.append(shared)

            else:  # PPTX
                targets = [
                    name
                    for name in archive.namelist()
                    if name.startswith("ppt/slides/slide")
                ]
                targets += [
                    name
                    for name in archive.namelist()
                    if name.startswith("ppt/notesSlides/notesSlide")
                ]

            for name in targets:
                try:
                    xml_data = archive.read(name)
                except KeyError:
                    continue
                text = self._xml_to_text(xml_data)
                if text.strip():
                    segments[name] = text

        return segments

    def _xml_to_text(self, xml_data: bytes) -> str:
        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError:
            return ""

        chunks: list[str] = []
        for node in root.iter():
            if node.text and node.text.strip():
                chunks.append(node.text.strip())
        return "\n".join(chunks)

    def _normalise_pii_types(
        self, pii_types: Sequence[str | PIIType] | None
    ) -> set[str] | None:
        if not pii_types:
            return None
        return {
            (ptype.value if isinstance(ptype, PIIType) else str(ptype)).lower()
            for ptype in pii_types
        }

    def _read_metadata(self, path: Path) -> Metadata:
        metadata = Metadata()

        with zipfile.ZipFile(path, "r") as archive:
            try:
                core = archive.read("docProps/core.xml")
                root = ET.fromstring(core)
                metadata.author = root.findtext(
                    "dc:creator", default=None, namespaces=self._CORE_NS
                )
                metadata.subject = root.findtext(
                    "dc:subject", default=None, namespaces=self._CORE_NS
                )
                metadata.title = root.findtext(
                    "dc:title", default=None, namespaces=self._CORE_NS
                )
                metadata.keywords = [
                    kw.strip()
                    for kw in (
                        root.findtext(
                            "cp:keywords", default="", namespaces=self._CORE_NS
                        )
                        or ""
                    ).split(",")
                    if kw.strip()
                ]
                metadata.modified_at = self._parse_datetime(
                    root.findtext("dcterms:modified", namespaces=self._CORE_NS)
                )
                metadata.created_at = self._parse_datetime(
                    root.findtext("dcterms:created", namespaces=self._CORE_NS)
                )
            except KeyError:
                pass

            try:
                app = archive.read("docProps/app.xml")
                root = ET.fromstring(app)
                ns = {
                    "ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
                }
                metadata.company = root.findtext(
                    "ep:Company", default=None, namespaces=ns
                )
                metadata.category = root.findtext(
                    "ep:Category", default=None, namespaces=ns
                )
            except KeyError:
                pass

        return metadata

    def _parse_datetime(self, raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            return None

    def _document_id(self, path: Path) -> str:
        stat = path.stat()
        fingerprint = f"{path.resolve()}::{stat.st_size}::{int(stat.st_mtime)}"
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _log_event(self, path: Path, action: str, details: dict | None = None) -> None:
        try:
            self.audit_log.log_access(
                document_id=self._document_id(path),
                document_path=str(path),
                user_id="system",
                action=action,
                details=details or {},
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.debug("Failed to record audit log entry: %s", exc)


__all__ = [
    "OfficeSecurityService",
    "OfficePIIMatch",
    "MacroCheckResult",
    "ExternalLinkReport",
    "MetadataSanitizationReport",
    "EncryptionResult",
]
