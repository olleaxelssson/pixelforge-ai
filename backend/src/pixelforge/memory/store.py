"""Character persistence: JSON records + reference-frame images on disk (D-011).

Mirrors ``ProjectStore``: one JSON file per character under the characters directory, with
reference-frame PNGs in a per-character subdirectory (never committed to git, per the artifact
policy).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from PIL import Image

from pixelforge.memory.models import Character, ReferenceFrame


class CharacterStore:
    def __init__(self, characters_dir: Path) -> None:
        self._dir = characters_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, character_id: str) -> Path:
        return self._dir / f"{character_id}.json"

    def frames_dir(self, character_id: str) -> Path:
        path = self._dir / character_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def list(self) -> list[Character]:
        characters = []
        for path in sorted(self._dir.glob("*.json")):
            try:
                characters.append(Character(**json.loads(path.read_text())))
            except (json.JSONDecodeError, ValueError):
                continue  # skip corrupt files; never block startup
        return sorted(characters, key=lambda c: c.updated_at, reverse=True)

    def get(self, character_id: str) -> Character | None:
        path = self._path(character_id)
        if not path.exists():
            return None
        return Character(**json.loads(path.read_text()))

    def save(self, character: Character) -> Character:
        character.updated_at = time.time()
        self._path(character.id).write_text(character.model_dump_json(indent=2))
        return character

    def delete(self, character_id: str) -> bool:
        path = self._path(character_id)
        if not path.exists():
            return False
        path.unlink()
        frames = self._dir / character_id
        if frames.exists():
            for file in frames.iterdir():
                file.unlink()
            frames.rmdir()
        return True

    def save_frame(self, character: Character, image: Image.Image, label: str) -> ReferenceFrame:
        """Write a reference-frame PNG and return its record (caller persists the character)."""
        index = len(character.reference_frames)
        filename = f"{label}_{index}.png"
        image.convert("RGBA").save(self.frames_dir(character.id) / filename)
        return ReferenceFrame(filename=filename, label=label)

    def load_frame(self, character: Character, frame: ReferenceFrame) -> Image.Image:
        return Image.open(self.frames_dir(character.id) / frame.filename).convert("RGBA")
