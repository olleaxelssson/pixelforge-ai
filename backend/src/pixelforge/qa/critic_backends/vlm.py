"""VLM critic backend (D-013): real perceptual/semantic judgment via a vision-language model.

Requires the ``[ml]`` extra (transformers + torch) and a model; like the FLUX backend it is
lazy-loaded and cached, and everything real stays behind ``is_available()`` so CI uses the mock.
The model is asked for a compact JSON assessment; parsing is defensive (a malformed reply degrades
to a neutral Critique rather than raising).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import numpy as np
from PIL import Image

from pixelforge.config import get_settings
from pixelforge.qa.critic_backends.base import CriticBackend
from pixelforge.qa.models import Critique, DetectorContext

logger = logging.getLogger("pixelforge.critic.vlm")

_PROMPT = (
    "You are a pixel-art art director. Judge this sprite. Intended subject: {subject}. "
    'Reply ONLY with JSON: {{"subject_match": 0..1, "appeal": 0..1, '
    '"verdict": "one short sentence", "notes": ["short note", ...]}}.'
)


def _clamp01(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


class VLMCriticBackend(CriticBackend):
    name = "vlm"

    def __init__(self) -> None:
        self._model: Any = None
        self._processor: Any = None

    def is_available(self) -> bool:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except ImportError:
            return False
        return True

    def _load(self) -> tuple[Any, Any]:
        if self._model is not None:
            return self._model, self._processor
        import torch
        from transformers import AutoModelForVision2Seq, AutoProcessor

        settings = get_settings()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("loading VLM critic %s on %s", settings.vlm_critic_model_id, device)
        self._processor = AutoProcessor.from_pretrained(settings.vlm_critic_model_id)
        self._model = AutoModelForVision2Seq.from_pretrained(
            settings.vlm_critic_model_id,
            torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
            cache_dir=settings.models_dir,
        ).to(device)
        return self._model, self._processor

    def _parse(self, text: str, subject: str | None) -> Critique:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        data: dict[str, Any] = {}
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                logger.warning("VLM critic returned unparseable JSON; using neutral critique")
        notes = data.get("notes") or []
        return Critique(
            backend=self.name,
            subject=subject,
            subject_match=_clamp01(data.get("subject_match")),
            appeal=_clamp01(data.get("appeal")),
            verdict=str(data.get("verdict", "")),
            notes=[str(n) for n in notes][:6],
        )

    def assess(self, rgba: np.ndarray, context: DetectorContext) -> Critique:
        model, processor = self._load()
        image = Image.fromarray(rgba.astype(np.uint8), "RGBA").convert("RGB")
        prompt = _PROMPT.format(subject=context.subject or "any game sprite")
        inputs = processor(images=image, text=prompt, return_tensors="pt").to(model.device)
        output = model.generate(**inputs, max_new_tokens=256)
        text = processor.batch_decode(output, skip_special_tokens=True)[0]
        return self._parse(text, context.subject)
