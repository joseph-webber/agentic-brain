# SPDX-License-Identifier: Apache-2.0

"""Tests for the Apple Pages processor."""

from __future__ import annotations

import plistlib
import zipfile
from pathlib import Path

import pytest


def _encode_varint(value: int) -> bytes:
    parts = bytearray()
    while True:
        to_write = value & 0x7F
        value >>= 7
        if value:
            parts.append(to_write | 0x80)
        else:
            parts.append(to_write)
            return bytes(parts)


def _proto_string_field(field_number: int, value: str) -> bytes:
    payload = value.encode("utf-8")
    key = (field_number << 3) | 2
    return _encode_varint(key) + _encode_varint(len(payload)) + payload


def _iwa_payload(*strings: str) -> bytes:
    message = b"".join(_proto_string_field(1, value) for value in strings)
    return _encode_varint(len(message)) + message


def _make_pages_package(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "Index/Document.iwa",
            _iwa_payload(
                "Project Plan",
                "First paragraph from IWA.",
                "Second paragraph from IWA.",
                "Pages 14.2",
            ),
        )
        archive.writestr(
            "Index/Tables/Tile-1.iwa",
            _iwa_payload("Name\tValue\nAlpha\t1\nBeta\t2"),
        )
        archive.writestr("Data/image-1.png", b"\x89PNG\r\n\x1a\n")
        archive.writestr("preview.jpg", b"\xff\xd8preview\xff\xd9")
        archive.writestr(
            "Metadata/DocumentIdentifier",
            b"doc-123",
        )
        archive.writestr(
            "Metadata/Properties.plist",
            plistlib.dumps(
                {
                    "author": "Joseph Webber",
                    "keywords": "planning,proposal",
                    "company": "Agentic Brain",
                    "creationDate": "2024-01-02T03:04:05",
                }
            ),
        )
    return path


def test_pages_processor_parses_iwa_content(tmp_path, office_modules) -> None:
    package = _make_pages_package(tmp_path / "sample.pages")
    processor = office_modules.apple_pages.PagesProcessor(use_textutil_fallback=False)

    document = processor.parse(package)

    assert document.format == office_modules.models.OfficeFormat.PAGES
    assert processor.extract_text().startswith("Project Plan")
    assert len(document.paragraphs) >= 2
    assert len(document.tables) == 1
    assert document.tables[0].rows[0][0].text_content() == "Name"
    assert document.tables[0].rows[1][1].text_content() == "1"
    assert len(processor.extract_images()) == 1
    assert processor.extract_images()[0].mime_type == "image/png"
    assert processor.get_preview() == b"\xff\xd8preview\xff\xd9"

    metadata = processor.get_metadata()
    assert metadata.title == "Project Plan"
    assert metadata.author == "Joseph Webber"
    assert metadata.company == "Agentic Brain"
    assert metadata.keywords == ["planning", "proposal"]
    assert metadata.created_at is not None


def test_pages_processor_to_pdf_uses_textutil_on_macos(
    tmp_path,
    monkeypatch,
    office_modules,
) -> None:
    package = _make_pages_package(tmp_path / "convert.pages")
    module = office_modules.apple_pages

    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        module.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name == "textutil" else None,
    )

    class _Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command, capture_output, text, timeout, check):
        output_index = command.index("-output") + 1
        Path(command[output_index]).write_bytes(b"%PDF-1.7")
        return _Result()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    processor = module.PagesProcessor(
        use_textutil_fallback=True, use_pages_automation=False
    )
    output = tmp_path / "out.pdf"

    result = processor.to_pdf(package, output)

    assert result == output.resolve()
    assert output.read_bytes() == b"%PDF-1.7"
