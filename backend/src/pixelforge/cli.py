"""Headless command-line interface for AI coding agents and scripts.

Runs the full generation pipeline synchronously (no server needed) and prints
machine-readable JSON to stdout. Examples:

    pixelforge generate "a knight with a flaming sword" --size 32 --seed 42
    pixelforge generate "health potion" --mode item --palette 8bit-console -o out/
    pixelforge export sprite.png --format unity --scale 4 -o exported/
    pixelforge list modes|styles|palettes|export-formats
    pixelforge system
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from pathlib import Path

from PIL import Image

from pixelforge.agents.planning_backends.registry import (
    get_planning_backend,
    list_planning_backends,
)
from pixelforge.agents.runtime import PlanningRuntime
from pixelforge.config import get_settings
from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.core.models import DitherMode, GenerationRequest
from pixelforge.exporters.base import ExportAsset, ExportOptions
from pixelforge.exporters.registry import get_exporter, list_exporters
from pixelforge.generation.backends.registry import list_backends
from pixelforge.generation.pipeline import GenerationPipeline
from pixelforge.generation.plan_compiler import compile_prompt
from pixelforge.models_manager.device import device_info
from pixelforge.modes.registry import ModeRegistry
from pixelforge.palettes.service import PaletteService
from pixelforge.styles.registry import StyleRegistry


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pixelforge", description="AI pixel art generation (headless)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate pixel art from a prompt")
    gen.add_argument("prompt")
    gen.add_argument("--mode", default="text-to-pixel")
    gen.add_argument("--style", default="modern-indie")
    gen.add_argument("--size", default="32", help="WIDTHxHEIGHT or a single number (e.g. 32x48)")
    gen.add_argument("--seed", type=int, default=None)
    gen.add_argument("--batch", type=int, default=1)
    gen.add_argument("--palette", default=None, help="Palette id to lock (see: list palettes)")
    gen.add_argument("--max-colors", type=int, default=16)
    gen.add_argument("--dither", choices=["none", "ordered"], default="none")
    gen.add_argument("--negative", default="", help="Negative prompt")
    gen.add_argument("--opaque", action="store_true", help="Disable transparent background")
    gen.add_argument("--reference", default=None, help="Path to a reference image")
    gen.add_argument("-o", "--output-dir", default=".", help="Directory for output PNGs")
    gen.add_argument("--quiet", action="store_true", help="Suppress progress on stderr")

    exp = sub.add_parser("export", help="Export image(s) to a game-ready format")
    exp.add_argument("images", nargs="+", help="Input PNG path(s); multiple = animation frames")
    exp.add_argument("--format", required=True, help="Format id (see: list export-formats)")
    exp.add_argument("--scale", type=int, default=1)
    exp.add_argument("--columns", type=int, default=None)
    exp.add_argument("--padding", type=int, default=0)
    exp.add_argument("--frame-duration-ms", type=int, default=120)
    exp.add_argument("--name", default="sprite", help="Base name for exported files")
    exp.add_argument("-o", "--output-dir", default=".")

    pln = sub.add_parser("plan", help="Produce the Scene Graph plan for a prompt (no image)")
    pln.add_argument("prompt")
    pln.add_argument("--mode", default="text-to-pixel")
    pln.add_argument("--style", default="modern-indie")
    pln.add_argument("--size", default="32", help="WIDTHxHEIGHT or a single number (e.g. 32x48)")
    pln.add_argument("--seed", type=int, default=None)
    pln.add_argument("--palette", default=None, help="Palette id to lock (see: list palettes)")
    pln.add_argument("--max-colors", type=int, default=16)
    pln.add_argument("--negative", default="", help="Negative prompt")
    pln.add_argument("--opaque", action="store_true", help="Disable transparent background")
    pln.add_argument("--planning-backend", default=None, help="Planning backend id (default: mock)")

    lst = sub.add_parser("list", help="List available catalog entries as JSON")
    lst.add_argument(
        "what",
        choices=["modes", "styles", "palettes", "export-formats", "backends", "planning-backends"],
    )

    sub.add_parser("system", help="Show device/backend availability as JSON")
    return parser


def _parse_size(value: str) -> tuple[int, int]:
    if "x" in value:
        w, h = value.lower().split("x", 1)
        return int(w), int(h)
    return int(value), int(value)


def _encode_reference(path: str | None) -> str | None:
    if path is None:
        return None
    image = Image.open(path).convert("RGBA")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def _cmd_generate(args: argparse.Namespace) -> int:
    settings = get_settings()
    width, height = _parse_size(args.size)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    modes = ModeRegistry()
    styles = StyleRegistry(user_dir=settings.user_styles_dir)
    planner = (
        PlanningRuntime(
            backend=get_planning_backend(settings.planning_backend), modes=modes, styles=styles
        )
        if settings.planning_enabled
        else None
    )
    pipeline = GenerationPipeline(
        backend_name=settings.backend,
        outputs_dir=output_dir,
        modes=modes,
        styles=styles,
        palettes=PaletteService(user_dir=settings.user_palettes_dir),
        diffusion_resolution=settings.diffusion_resolution,
        diffusion_steps=settings.diffusion_steps,
        planner=planner,
    )
    request = GenerationRequest(
        prompt=args.prompt,
        negative_prompt=args.negative,
        mode=args.mode,
        style=args.style,
        width=width,
        height=height,
        seed=args.seed,
        batch_size=args.batch,
        palette_id=args.palette,
        max_colors=args.max_colors,
        dither=DitherMode(args.dither),
        transparent_background=not args.opaque,
        reference_image_base64=_encode_reference(args.reference),
    )

    def on_progress(stage: str, percent: float) -> None:
        if not args.quiet:
            print(f"{stage} {percent:.0f}%", file=sys.stderr)

    result = pipeline.run("cli", request, on_progress)
    output = {
        "images": [
            {**image.model_dump(), "path": str(output_dir / image.filename)}
            for image in result.images
        ]
    }
    print(json.dumps(output, indent=2))
    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    settings = get_settings()
    width, height = _parse_size(args.size)
    modes = ModeRegistry()
    styles = StyleRegistry(user_dir=settings.user_styles_dir)
    runtime = PlanningRuntime(
        backend=get_planning_backend(args.planning_backend or settings.planning_backend),
        modes=modes,
        styles=styles,
    )
    request = GenerationRequest(
        prompt=args.prompt,
        negative_prompt=args.negative,
        mode=args.mode,
        style=args.style,
        width=width,
        height=height,
        seed=args.seed,
        palette_id=args.palette,
        max_colors=args.max_colors,
        transparent_background=not args.opaque,
    )
    style = styles.get(request.style)
    graph = runtime.plan(request)
    graph.provenance.expanded_prompt = compile_prompt(graph, style)
    print(json.dumps(graph.model_dump(mode="json"), indent=2))
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    exporter = get_exporter(args.format)
    frames = [Image.open(path).convert("RGBA") for path in args.images]
    options = ExportOptions(
        scale=args.scale,
        columns=args.columns,
        padding=args.padding,
        frame_duration_ms=args.frame_duration_ms,
        base_name=args.name,
    )
    dest = Path(args.output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    paths = exporter.export(ExportAsset(frames=frames), options, dest)
    print(json.dumps({"files": [str(p) for p in paths]}, indent=2))
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    settings = get_settings()
    payload: object
    if args.what == "modes":
        payload = [m.model_dump() for m in ModeRegistry().list()]
    elif args.what == "styles":
        payload = [s.model_dump() for s in StyleRegistry(user_dir=settings.user_styles_dir).list()]
    elif args.what == "palettes":
        payload = [
            p.model_dump() for p in PaletteService(user_dir=settings.user_palettes_dir).list()
        ]
    elif args.what == "export-formats":
        payload = list_exporters()
    elif args.what == "planning-backends":
        payload = list_planning_backends()
    else:
        payload = list_backends()
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_system(_: argparse.Namespace) -> int:
    settings = get_settings()
    print(
        json.dumps(
            {
                "device": device_info(),
                "backends": list_backends(),
                "data_dir": str(settings.data_dir),
            },
            indent=2,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    handlers = {
        "generate": _cmd_generate,
        "plan": _cmd_plan,
        "export": _cmd_export,
        "list": _cmd_list,
        "system": _cmd_system,
    }
    try:
        return handlers[args.command](args)
    except UnknownRegistryKeyError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
