"""CharacterMemory: the Tier-1 identity service (D-011).

Responsibilities:
- persist characters (store) and their reference frames;
- maintain the canonical identity embedding (from the "passport" frame);
- **apply** a character to a `GenerationRequest` — inject the identity subject, lock the palette,
  and attach the canonical frame as the reference image (inference-time conditioning, no training);
- **check drift** — embed a candidate sprite and compare against the canonical embedding.

The identity phrase prepends the character's fixed slots to the user's variation ("winter armor"),
so "Captain Elias winter armor" always carries the same canonical identity text; combined with the
palette lock and reference conditioning this is the Tier-1 anti-drift stack from the ADR.
"""

from __future__ import annotations

import base64
import io

from PIL import Image

from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.core.models import GenerationRequest
from pixelforge.memory.drift import cosine_similarity
from pixelforge.memory.embeddings import EmbeddingBackend
from pixelforge.memory.models import Character, CharacterIdentity, DriftResult
from pixelforge.memory.store import CharacterStore


class CharacterMemory:
    def __init__(
        self,
        store: CharacterStore,
        embeddings: EmbeddingBackend,
        drift_threshold: float = 0.85,
    ) -> None:
        self._store = store
        self._embeddings = embeddings
        self._threshold = drift_threshold

    # -- CRUD ----------------------------------------------------------------

    def list(self) -> list[Character]:
        return self._store.list()

    def get(self, character_id: str) -> Character:
        character = self._store.get(character_id)
        if character is None:
            raise UnknownRegistryKeyError(f"unknown character: {character_id}")
        return character

    def create(
        self, name: str, identity: CharacterIdentity, palette_id: str | None = None
    ) -> Character:
        return self._store.save(Character(name=name, identity=identity, palette_id=palette_id))

    def save(self, character: Character) -> Character:
        return self._store.save(character)

    def delete(self, character_id: str) -> bool:
        return self._store.delete(character_id)

    # -- reference frames + embedding -----------------------------------------

    def add_reference_frame(
        self, character_id: str, image: Image.Image, label: str = "variant"
    ) -> Character:
        """Store a frame; the first frame (or an explicit "passport") anchors the embedding."""
        character = self.get(character_id)
        frame = self._store.save_frame(character, image, label)
        character.reference_frames.append(frame)
        if label == "passport" or len(character.reference_frames) == 1:
            character.embedding = self._embeddings.embed(image)
            character.embedding_backend = self._embeddings.name
        return self._store.save(character)

    # -- Tier-1 identity application -------------------------------------------

    def identity_phrase(self, character: Character) -> str:
        identity = character.identity
        pieces = [identity.subject]
        if identity.proportions:
            pieces.append(identity.proportions)
        if identity.silhouette:
            pieces.append(identity.silhouette)
        equipment = [p.name for p in identity.parts if p.name != "body"]
        if equipment:
            pieces.append("with " + ", ".join(equipment))
        return ", ".join(pieces)

    def apply_to_request(self, character_id: str, request: GenerationRequest) -> GenerationRequest:
        """Return a copy of ``request`` carrying the character's identity.

        The user prompt becomes the *variation* ("winter armor"); the canonical identity phrase is
        prepended so the diffusion prompt is stable across generations. The character's palette is
        locked unless the request explicitly chose one, and the canonical reference frame rides
        along as the Stage-A reference image.
        """
        character = self.get(character_id)
        variation = request.prompt.strip()
        prompt = self.identity_phrase(character)
        if variation:
            prompt = f"{prompt}, {variation}"

        updates: dict[str, object] = {"prompt": prompt, "mode": "character"}
        if character.palette_id and not request.palette_id:
            updates["palette_id"] = character.palette_id

        frame = character.canonical_frame()
        if frame is not None and not request.reference_image_base64:
            image = self._store.load_frame(character, frame)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            updates["reference_image_base64"] = base64.b64encode(buffer.getvalue()).decode()

        return request.model_copy(update=updates)

    # -- drift gate ------------------------------------------------------------

    def check_drift(self, character_id: str, image: Image.Image) -> DriftResult:
        character = self.get(character_id)
        if not character.embedding:
            raise ValueError(
                f"character '{character.name}' has no reference frame; add one before drift checks"
            )
        similarity = cosine_similarity(character.embedding, self._embeddings.embed(image))
        return DriftResult(
            character_id=character_id,
            similarity=round(similarity, 4),
            threshold=self._threshold,
            consistent=similarity >= self._threshold,
        )
