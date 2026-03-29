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

from __future__ import annotations

import json
import os
import shutil
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

VOICE_LIBRARY_ENV_VAR = "AGENTIC_BRAIN_VOICE_CLONE_DIR"

KNOWN_LADIES = (
    "alice",
    "dewi",
    "flo",
    "kanya",
    "karen",
    "kyoko",
    "linh",
    "moira",
    "sari",
    "shelley",
    "tingting",
    "wayan",
    "yuna",
    "zosia",
)

SYSTEM_VOICE_BY_LADY = {
    "alice": "Alice",
    "dewi": "Damayanti",
    "flo": "Amelie",
    "kanya": "Kanya",
    "karen": "Karen (Premium)",
    "kyoko": "Kyoko",
    "linh": "Linh",
    "moira": "Moira",
    "sari": "Damayanti",
    "shelley": "Shelley",
    "tingting": "Tingting",
    "wayan": "Damayanti",
    "yuna": "Yuna",
    "zosia": "Zosia",
}


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    parts = [part for part in cleaned.split("-") if part]
    return "-".join(parts) or "voice"


def resolve_voice_storage_dir(base_dir: str | Path | None = None) -> Path:
    if base_dir is not None:
        return Path(base_dir).expanduser()

    configured = os.getenv(VOICE_LIBRARY_ENV_VAR, "").strip()
    if configured:
        return Path(configured).expanduser()

    return Path.home() / ".agentic-brain" / "voices"


@dataclass(slots=True)
class VoiceProfile:
    voice_id: str
    name: str
    reference_audio_path: str
    reference_text: str = ""
    assigned_lady: str | None = None
    backend: str = "stored-reference"
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    validation: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def reference_audio(self) -> Path:
        return Path(self.reference_audio_path)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoiceProfile:
        return cls(
            voice_id=data["voice_id"],
            name=data["name"],
            reference_audio_path=data["reference_audio_path"],
            reference_text=data.get("reference_text", ""),
            assigned_lady=data.get("assigned_lady"),
            backend=data.get("backend", "stored-reference"),
            created_at=data.get("created_at", _utc_now_iso()),
            updated_at=data.get("updated_at", _utc_now_iso()),
            validation=dict(data.get("validation", {})),
            metadata=dict(data.get("metadata", {})),
        )


class VoiceLibrary:
    def __init__(self, base_dir: str | Path | None = None) -> None:
        self.base_dir = resolve_voice_storage_dir(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def available_ladies(self) -> tuple[str, ...]:
        return KNOWN_LADIES

    def generate_voice_id(self, name: str) -> str:
        return f"{_slugify(name)}-{uuid4().hex[:8]}"

    def voice_dir(self, voice_id: str) -> Path:
        return self.base_dir / voice_id

    def profile_path(self, voice_id: str) -> Path:
        return self.voice_dir(voice_id) / "profile.json"

    def save_profile(self, profile: VoiceProfile) -> VoiceProfile:
        profile.updated_at = _utc_now_iso()
        target_dir = self.voice_dir(profile.voice_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        self.profile_path(profile.voice_id).write_text(
            json.dumps(profile.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return profile

    def register_voice(
        self,
        *,
        source_audio: str | Path,
        name: str,
        reference_text: str = "",
        assigned_lady: str | None = None,
        backend: str = "stored-reference",
        validation: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> VoiceProfile:
        source = Path(source_audio).expanduser()
        voice_id = self.generate_voice_id(name)
        voice_dir = self.voice_dir(voice_id)
        voice_dir.mkdir(parents=True, exist_ok=True)

        copied_reference = voice_dir / f"reference{source.suffix.lower() or '.wav'}"
        shutil.copy2(source, copied_reference)

        normalized_lady = assigned_lady.lower() if assigned_lady else None
        if normalized_lady and normalized_lady not in KNOWN_LADIES:
            raise ValueError(f"Unknown lady '{assigned_lady}'")

        profile = VoiceProfile(
            voice_id=voice_id,
            name=name,
            reference_audio_path=str(copied_reference),
            reference_text=reference_text,
            assigned_lady=normalized_lady,
            backend=backend,
            validation=validation or {},
            metadata=metadata or {},
        )
        return self.save_profile(profile)

    def get_voice(self, voice_id: str) -> VoiceProfile | None:
        profile_file = self.profile_path(voice_id)
        if not profile_file.exists():
            return None
        return VoiceProfile.from_dict(
            json.loads(profile_file.read_text(encoding="utf-8"))
        )

    def list_voices(self) -> list[VoiceProfile]:
        profiles: list[VoiceProfile] = []
        for profile_file in sorted(self.base_dir.glob("*/profile.json")):
            profiles.append(
                VoiceProfile.from_dict(
                    json.loads(profile_file.read_text(encoding="utf-8"))
                )
            )
        return sorted(profiles, key=lambda item: (item.name.lower(), item.voice_id))

    def delete_voice(self, voice_id: str) -> bool:
        voice_dir = self.voice_dir(voice_id)
        if not voice_dir.exists():
            return False
        shutil.rmtree(voice_dir)
        return True

    def assign_voice(self, voice_id: str, lady: str) -> VoiceProfile:
        normalized_lady = lady.strip().lower()
        if normalized_lady not in KNOWN_LADIES:
            raise ValueError(f"Unknown lady '{lady}'")

        profile = self.get_voice(voice_id)
        if profile is None:
            raise KeyError(voice_id)

        profile.assigned_lady = normalized_lady
        profile.metadata.setdefault(
            "fallback_voice", SYSTEM_VOICE_BY_LADY[normalized_lady]
        )
        return self.save_profile(profile)

    def find_by_lady(self, lady: str) -> list[VoiceProfile]:
        normalized_lady = lady.strip().lower()
        return [
            profile
            for profile in self.list_voices()
            if profile.assigned_lady == normalized_lady
        ]

    def export_voice(self, voice_id: str, export_path: str | Path) -> Path:
        profile = self.get_voice(voice_id)
        if profile is None:
            raise KeyError(voice_id)

        export_target = Path(export_path).expanduser()
        export_target.parent.mkdir(parents=True, exist_ok=True)

        portable_profile = profile.to_dict()
        portable_profile["reference_audio_path"] = (
            f"audio/{profile.reference_audio.name}"
        )

        with zipfile.ZipFile(
            export_target, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            archive.writestr(
                "profile.json",
                json.dumps(portable_profile, indent=2, sort_keys=True),
            )
            archive.write(
                profile.reference_audio,
                arcname=portable_profile["reference_audio_path"],
            )

        return export_target

    def import_voice(self, import_path: str | Path) -> VoiceProfile:
        source = Path(import_path).expanduser()
        with zipfile.ZipFile(source, "r") as archive:
            profile_data = json.loads(archive.read("profile.json").decode("utf-8"))
            original_audio_path = Path(profile_data["reference_audio_path"])
            voice_id = profile_data.get("voice_id") or self.generate_voice_id(
                profile_data.get("name", "voice")
            )
            if self.voice_dir(voice_id).exists():
                voice_id = self.generate_voice_id(profile_data.get("name", "voice"))

            target_dir = self.voice_dir(voice_id)
            target_dir.mkdir(parents=True, exist_ok=True)
            target_audio_path = target_dir / original_audio_path.name
            target_audio_path.write_bytes(
                archive.read(profile_data["reference_audio_path"])
            )

        profile_data["voice_id"] = voice_id
        profile_data["reference_audio_path"] = str(target_audio_path)
        profile = VoiceProfile.from_dict(profile_data)
        profile.metadata["imported_from"] = str(source)
        return self.save_profile(profile)


__all__ = [
    "KNOWN_LADIES",
    "SYSTEM_VOICE_BY_LADY",
    "VOICE_LIBRARY_ENV_VAR",
    "VoiceLibrary",
    "VoiceProfile",
    "resolve_voice_storage_dir",
]
