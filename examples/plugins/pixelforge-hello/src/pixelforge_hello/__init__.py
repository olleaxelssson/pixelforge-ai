"""Sample PixelForge plugin (D-014): proves the entry-point contract end to end.

Ships two components:

- ``AsciiArtExporter`` — exports each frame as ASCII art (``.txt``), one character per pixel.
- ``CheckerboardDetector`` — an advise-only QA detector flagging dense 2x2 checkerboard noise.

Install with ``pip install -e examples/plugins/pixelforge-hello``, then enable it:
``PIXELFORGE_PLUGINS_ENABLED=true PIXELFORGE_PLUGIN_ALLOWLIST='["pixelforge-hello"]'``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from pixelforge.core.scene_graph import Finding, FindingSeverity, Region
from pixelforge.exporters.base import ExportAsset, Exporter, ExportOptions
from pixelforge.plugins.manifest import PluginManifest
from pixelforge.qa.detectors.base import Detector, opaque_mask
from pixelforge.qa.models import DetectorContext

MANIFEST = PluginManifest(
    name="pixelforge-hello",
    version="0.1.0",
    author="PixelForge examples",
    description="ASCII-art exporter + checkerboard-noise QA detector",
    api_version="1.0",
    capabilities=["filesystem"],  # the exporter writes files; no network access
)

# Dark → light luminance ramp, one character per pixel.
_RAMP = " .:-=+*#%@"


class AsciiArtExporter(Exporter):
    format_id = "ascii"
    display_name = "ASCII Art (.txt)"

    def export(self, asset: ExportAsset, options: ExportOptions, dest: Path) -> list[Path]:
        paths: list[Path] = []
        for index, frame in enumerate(asset.frames):
            rgba = np.asarray(frame.convert("RGBA"), dtype=np.float64)
            luma = 0.299 * rgba[..., 0] + 0.587 * rgba[..., 1] + 0.114 * rgba[..., 2]
            visible = rgba[..., 3] > 0
            lines = []
            for y in range(rgba.shape[0]):
                chars = []
                for x in range(rgba.shape[1]):
                    if not visible[y, x]:
                        chars.append(" ")
                    else:
                        chars.append(_RAMP[min(int(luma[y, x] / 256 * len(_RAMP)), len(_RAMP) - 1)])
                lines.append("".join(chars))
            path = dest / f"{options.base_name}_{index}.txt"
            path.write_text("\n".join(lines) + "\n")
            paths.append(path)
        return paths


class CheckerboardDetector(Detector):
    """Flags sprites where many 2x2 blocks alternate colors perfectly (dither noise)."""

    name = "checkerboard-noise"
    repairable = False

    def detect(self, rgba: np.ndarray, context: DetectorContext) -> list[Finding]:
        opaque = opaque_mask(rgba)
        rgb = rgba[..., :3]
        height, width = opaque.shape
        checkered = total = 0
        for y in range(0, height - 1, 2):
            for x in range(0, width - 1, 2):
                if not opaque[y : y + 2, x : x + 2].all():
                    continue
                total += 1
                a, b = rgb[y, x], rgb[y, x + 1]
                if (
                    not np.array_equal(a, b)
                    and np.array_equal(a, rgb[y + 1, x + 1])
                    and np.array_equal(b, rgb[y + 1, x])
                ):
                    checkered += 1
        if total >= 8 and checkered / total > 0.5:
            return [
                Finding(
                    detector=self.name,
                    severity=FindingSeverity.WARNING,
                    message=f"checkerboard dithering covers {checkered}/{total} blocks",
                    region=Region(x=0, y=0, width=width, height=height),
                )
            ]
        return []
