"""Vision-language description with a quality-first, optional-API architecture.

- **local** (default, no key): derives a caption and tags deterministically from the numeric
  analysis. Always available, instant, offline.
- **anthropic / openai** (opt-in via ``STUDYLAB_VLM_PROVIDER`` + ``STUDYLAB_VLM_API_KEY``): sends the
  image to a hosted vision model for richer captions/tags. Keys come from the environment only and
  are never stored. Any failure falls back to local mode, so the app never hard-depends on a key.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from studylab.logging_setup import get_logger

log = get_logger("vlm")


@dataclass
class VlmResult:
    caption: str
    tags: list[str] = field(default_factory=list)
    provider: str = "local"


def _size_word(eff: int) -> str:
    if eff <= 16:
        return "tiny"
    if eff <= 32:
        return "small"
    if eff <= 64:
        return "medium"
    return "large"


def local_describe(analysis: dict[str, Any]) -> VlmResult:
    p, a, f = analysis["palette"], analysis["pixel_art"], analysis["frames"]
    eff = max(a["effective_width"], a["effective_height"])
    tags: list[str] = []
    if a["is_pixel_art"]:
        tags.append("pixel-art")
    tags.append(f"{a['effective_width']}x{a['effective_height']}")
    tags.append(f"{p['color_count']}-color")
    if p["color_count"] <= 16:
        tags.append("low-palette")
    if p["contrast_range"] >= 0.4:
        tags.append("high-contrast")
    if a["outline_ratio"] >= 0.3:
        tags.append("outlined")
    if a["dithering"] >= 0.03:
        tags.append("dithered")
    if a["tileable_h"] >= 0.92 and a["tileable_v"] >= 0.92:
        tags.append("tileable")
    if f["is_animation"]:
        tags.append("animated")
    if f["is_sheet"]:
        tags.append("sprite-sheet")
    if a["transparent_ratio"] > 0.1:
        tags.append("transparent-bg")

    sil = (
        "compact silhouette"
        if a["silhouette_compactness"] >= 0.5 and a["silhouette_coverage"] < 0.9
        else "full-frame"
        if a["silhouette_coverage"] >= 0.9
        else "sparse silhouette"
    )
    caption = (
        f"{_size_word(eff)} {'pixel-art ' if a['is_pixel_art'] else ''}image, "
        f"{p['color_count']}-colour palette, {sil}"
    )
    if f["is_animation"]:
        caption += f", animated ({f['frame_count']} frames)"
    elif f["is_sheet"]:
        caption += f", sprite sheet ({f['columns']}×{f['rows']})"
    if a["tileable_h"] >= 0.92 and a["tileable_v"] >= 0.92:
        caption += ", tiles seamlessly"
    return VlmResult(caption=caption + ".", tags=tags, provider="local")


def describe(image_path: Path, analysis: dict[str, Any], provider: str, api_key: str | None) -> VlmResult:
    """Describe an image, preferring the configured provider but always succeeding (local fallback)."""
    if provider == "local" or not api_key:
        return local_describe(analysis)
    try:
        if provider == "anthropic":
            return _anthropic_describe(image_path, api_key, analysis)
        if provider == "openai":
            return _openai_describe(image_path, api_key, analysis)
    except Exception as exc:  # noqa: BLE001 — never let a remote call break analysis
        log.warning("VLM provider '%s' failed (%s); using local description", provider, exc)
    return local_describe(analysis)


def _image_b64(image_path: Path) -> str:
    import base64

    return base64.b64encode(image_path.read_bytes()).decode()


_PROMPT = (
    "You are cataloguing a pixel-art reference for study. In one sentence, describe the subject and "
    "style, then list 3-8 short lowercase tags. Respond as JSON: {\"caption\": str, \"tags\": [str]}."
)


def _anthropic_describe(image_path: Path, api_key: str, analysis: dict[str, Any]) -> VlmResult:
    import json
    import urllib.request

    body = json.dumps(
        {
            "model": "claude-3-5-sonnet-latest",
            "max_tokens": 400,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": _image_b64(image_path),
                            },
                        },
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (fixed trusted host)
        payload = json.loads(resp.read())
    text = payload["content"][0]["text"]
    return _parse_vlm_json(text, "anthropic", analysis)


def _openai_describe(image_path: Path, api_key: str, analysis: dict[str, Any]) -> VlmResult:
    import json
    import urllib.request

    data_url = "data:image/png;base64," + _image_b64(image_path)
    body = json.dumps(
        {
            "model": "gpt-4o-mini",
            "max_tokens": 400,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={"authorization": f"Bearer {api_key}", "content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        payload = json.loads(resp.read())
    text = payload["choices"][0]["message"]["content"]
    return _parse_vlm_json(text, "openai", analysis)


def _parse_vlm_json(text: str, provider: str, analysis: dict[str, Any]) -> VlmResult:
    import json
    import re

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return local_describe(analysis)
    data = json.loads(match.group(0))
    tags = [str(t).strip().lower() for t in data.get("tags", []) if str(t).strip()]
    return VlmResult(caption=str(data.get("caption", "")).strip(), tags=tags, provider=provider)
