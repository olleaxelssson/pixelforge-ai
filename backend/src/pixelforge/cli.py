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
from pixelforge.core.errors import PixelForgeError, UnknownRegistryKeyError
from pixelforge.core.models import DitherMode, GenerationRequest
from pixelforge.dataset.builder import build_dataset, scan_directory
from pixelforge.dataset.phash import DEFAULT_DUP_DISTANCE
from pixelforge.exporters.base import ExportAsset, ExportOptions
from pixelforge.exporters.registry import get_exporter, list_exporters
from pixelforge.generation.backends.registry import list_backends
from pixelforge.generation.pipeline import GenerationPipeline
from pixelforge.generation.plan_compiler import compile_prompt
from pixelforge.memory.embeddings import get_embedding_backend
from pixelforge.memory.models import CharacterIdentity
from pixelforge.memory.service import CharacterMemory
from pixelforge.memory.store import CharacterStore
from pixelforge.models_manager.device import device_info
from pixelforge.modes.registry import ModeRegistry
from pixelforge.palettes.analysis import (
    analyze_palette,
    compress_palette,
    simulate_cvd_palette,
)
from pixelforge.palettes.service import PaletteService
from pixelforge.plugins.loader import load_plugins
from pixelforge.qa.engine import QAEngine
from pixelforge.qa.models import DetectorContext
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
    gen.add_argument(
        "--tileable", action="store_true", help="Seam-blend edges so the sprite tiles seamlessly"
    )
    gen.add_argument("--reference", default=None, help="Path to a reference image")
    gen.add_argument("--character", default=None, help="Stored character id (identity memory)")
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

    pal = sub.add_parser("palette", help="Analyze/transform a palette (contrast, CVD, readability)")
    pal.add_argument("palette_id", help="Palette id (see: list palettes)")
    pal.add_argument("--compress", type=int, default=None, metavar="N", help="Compress to N colors")
    pal.add_argument(
        "--simulate",
        default=None,
        metavar="VISION",
        help="Simulate a color-vision deficiency: protanopia|deuteranopia|tritanopia",
    )

    qac = sub.add_parser("qa", help="Run the pixel QA engine on an image (report as JSON)")
    qac.add_argument("image", help="Path to a PNG sprite")
    qac.add_argument("--max-colors", type=int, default=16, help="Color budget for overflow checks")
    qac.add_argument("--palette", default=None, help="Locked palette id (see: list palettes)")
    qac.add_argument("--lighting", default=None, help="Intended light direction, e.g. top-left")
    qac.add_argument(
        "--subject",
        default=None,
        help="Intended subject (enables the semantic critic if configured)",
    )
    qac.add_argument(
        "--critic", default=None, choices=["heuristic", "vlm"], help="Override the QA critic"
    )
    qac.add_argument(
        "--opaque", action="store_true", help="Sprite is not on a transparent background"
    )
    qac.add_argument(
        "--tileable", action="store_true", help="Check the tiling seam (edge-wrap discontinuity)"
    )
    qac.add_argument(
        "--repair", action="store_true", help="Apply safe repairs and write the result"
    )
    qac.add_argument(
        "--repair-loop",
        action="store_true",
        help="Layer 2: regenerate failing regions in a bounded loop (implies --repair output)",
    )
    qac.add_argument(
        "--max-iter", type=int, default=2, help="Max repair-loop iterations (with --repair-loop)"
    )
    qac.add_argument("-o", "--output", default=None, help="Output path for the repaired PNG")

    anim = sub.add_parser("animate", help="Generate an animation frame sequence (GIF + sheet)")
    anim.add_argument("prompt")
    anim.add_argument("--action", default="idle", help="Action id (see: list actions)")
    anim.add_argument("--mode", default="character")
    anim.add_argument("--style", default="modern-indie")
    anim.add_argument("--size", default="32", help="WIDTHxHEIGHT or a single number")
    anim.add_argument("--seed", type=int, default=None)
    anim.add_argument("--palette", default=None, help="Palette id to lock (see: list palettes)")
    anim.add_argument("--max-colors", type=int, default=16)
    anim.add_argument("--frame-ms", type=int, default=120, help="Frame duration (ms) for the GIF")
    anim.add_argument("--qa", action="store_true", help="Run QA on each frame")
    anim.add_argument(
        "--reference-chain",
        action="store_true",
        help="Feed each frame the previous one as a Stage-A reference (img2img)",
    )
    anim.add_argument(
        "--consistency", action="store_true", help="Measure per-frame identity drift vs frame 1"
    )
    anim.add_argument("-o", "--output-dir", default=".", help="Directory for frames/GIF/sheet")

    chr_parser = sub.add_parser("character", help="Manage stored characters (identity memory)")
    chr_sub = chr_parser.add_subparsers(dest="character_command", required=True)
    chr_create = chr_sub.add_parser("create", help="Create a character")
    chr_create.add_argument("name")
    chr_create.add_argument("--subject", required=True, help='e.g. "Captain Elias, veteran knight"')
    chr_create.add_argument("--proportions", default="", help='e.g. "tall, broad-shouldered"')
    chr_create.add_argument("--silhouette", default="", help='e.g. "horned helm, long cape"')
    chr_create.add_argument("--palette", default=None, help="Palette id to lock for this character")
    chr_sub.add_parser("list", help="List stored characters")
    chr_frame = chr_sub.add_parser("add-frame", help="Attach a reference frame image")
    chr_frame.add_argument("character_id")
    chr_frame.add_argument("image", help="Path to a PNG reference frame")
    chr_frame.add_argument(
        "--label", default="passport", help='"passport" anchors the identity embedding'
    )
    chr_drift = chr_sub.add_parser("drift", help="Check a sprite against the stored identity")
    chr_drift.add_argument("character_id")
    chr_drift.add_argument("image", help="Path to the candidate sprite PNG")

    lst = sub.add_parser("list", help="List available catalog entries as JSON")
    lst.add_argument(
        "what",
        choices=[
            "modes",
            "styles",
            "palettes",
            "export-formats",
            "backends",
            "planning-backends",
            "plugins",
            "actions",
        ],
    )

    bench = sub.add_parser(
        "benchmark", help="Run the benchmark suite through the active backend (quality + timing)"
    )
    bench.add_argument("--backend", default=None, help="Override backend (mock|flux-schnell|auto)")
    bench.add_argument("-o", "--output", default=None, help="Write the JSON report to this path")

    tset = sub.add_parser(
        "tileset", help="Generate a coherent, seam-locked terrain tile family + auto-tile sheet"
    )
    tset.add_argument("prompt")
    tset.add_argument("--variants", type=int, default=4, help="Number of tiles in the family")
    tset.add_argument("--mode", default="tileset")
    tset.add_argument("--style", default="modern-indie")
    tset.add_argument("--size", default="32", help="WIDTHxHEIGHT or a single number")
    tset.add_argument("--seed", type=int, default=None)
    tset.add_argument("--palette", default=None, help="Palette id to lock (see: list palettes)")
    tset.add_argument("--max-colors", type=int, default=16)
    tset.add_argument("-o", "--output-dir", default=".", help="Directory for tiles + blob sheet")

    proj = sub.add_parser("project", help="Save/load/inspect a portable .pforge project bundle")
    proj_sub = proj.add_subparsers(dest="project_command", required=True)
    proj_save = proj_sub.add_parser("save", help="Bundle a folder of sprites into a .pforge file")
    proj_save.add_argument("file", help="Output .pforge path")
    proj_save.add_argument("--sprites", required=True, help="Folder of PNG sprites to bundle")
    proj_save.add_argument("--name", default="Untitled Project", help="Project name")
    proj_load = proj_sub.add_parser("load", help="Extract a .pforge file's manifest + sprites")
    proj_load.add_argument("file", help="Input .pforge path")
    proj_load.add_argument("-o", "--output-dir", required=True, help="Directory to extract into")
    proj_info = proj_sub.add_parser("info", help="Print a .pforge file's manifest summary")
    proj_info.add_argument("file", help="Input .pforge path")

    ds = sub.add_parser("dataset", help="Build a LoRA training dataset from a folder of sprites")
    ds_sub = ds.add_subparsers(dest="dataset_command", required=True)
    ds_build = ds_sub.add_parser(
        "build", help="Validate, dedup, caption, and emit a training manifest + LoRA config"
    )
    ds_build.add_argument("directory", help="Folder of sprite images (scanned recursively)")
    ds_build.add_argument(
        "--dup-distance",
        type=int,
        default=DEFAULT_DUP_DISTANCE,
        help="Max Hamming distance (of 64) for near-duplicates",
    )
    ds_build.add_argument(
        "-o", "--output-dir", default=None, help="Write manifest.jsonl + lora_config.json here"
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


def _character_memory(settings) -> CharacterMemory:
    return CharacterMemory(
        store=CharacterStore(characters_dir=settings.characters_dir),
        embeddings=get_embedding_backend(settings.memory_embedding_backend),
        drift_threshold=settings.memory_drift_threshold,
    )


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
        tileable=args.tileable,
        reference_image_base64=_encode_reference(args.reference),
    )
    if args.character:
        request = _character_memory(settings).apply_to_request(args.character, request)

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


def _cmd_palette(args: argparse.Namespace) -> int:
    settings = get_settings()
    palettes = PaletteService(user_dir=settings.user_palettes_dir)
    palette = palettes.get(args.palette_id)
    if args.compress is not None:
        payload: object = compress_palette(palette, args.compress).model_dump()
    elif args.simulate is not None:
        payload = simulate_cvd_palette(palette, args.simulate).model_dump()
    else:
        payload = analyze_palette(palette).model_dump()
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_qa(args: argparse.Namespace) -> int:
    settings = get_settings()
    image = Image.open(args.image).convert("RGBA")
    palette = None
    if args.palette:
        palette = PaletteService(user_dir=settings.user_palettes_dir).get(args.palette).as_rgb()
    context = DetectorContext(
        max_colors=args.max_colors,
        transparent_background=not args.opaque,
        palette=palette,
        lighting_direction=args.lighting,
        subject=args.subject,
        tileable=args.tileable,
    )
    critic_kind = args.critic or settings.qa_critic
    if critic_kind == "vlm":
        from pixelforge.qa.critic import VLMCritic
        from pixelforge.qa.critic_backends.registry import get_critic_backend

        critic = VLMCritic(get_critic_backend(settings.vlm_critic_backend))
        engine = QAEngine(critic=critic, pass_threshold=settings.qa_pass_threshold)
    else:
        engine = QAEngine(pass_threshold=settings.qa_pass_threshold)
    if args.repair_loop:
        from pixelforge.qa.repair_loop import RepairLoop

        final, loop_report = RepairLoop(engine=engine, max_iterations=max(1, args.max_iter)).run(
            image, context
        )
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            final.save(args.output)
        payload: object = {"repair_loop": loop_report.model_dump(), "output": args.output}
    elif args.repair:
        repaired, report = engine.repair(image, context)
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            repaired.save(args.output)
        payload = {"report": report.model_dump(), "output": args.output}
    else:
        payload = engine.run(image, context).model_dump()
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_animate(args: argparse.Namespace) -> int:
    from pixelforge.animation.sequence import AnimationRequest, AnimationSequence

    settings = get_settings()
    width, height = _parse_size(args.size)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    modes = ModeRegistry()
    styles = StyleRegistry(user_dir=settings.user_styles_dir)
    pipeline = GenerationPipeline(
        backend_name=settings.backend,
        outputs_dir=output_dir,
        modes=modes,
        styles=styles,
        palettes=PaletteService(user_dir=settings.user_palettes_dir),
        diffusion_resolution=settings.diffusion_resolution,
        diffusion_steps=settings.diffusion_steps,
    )
    sequence = AnimationSequence(
        pipeline=pipeline,
        outputs_dir=output_dir,
        qa_engine=QAEngine(pass_threshold=settings.qa_pass_threshold) if args.qa else None,
        embeddings=get_embedding_backend(settings.memory_embedding_backend),
        drift_threshold=settings.memory_drift_threshold,
    )
    request = AnimationRequest(
        prompt=args.prompt,
        action=args.action,
        mode=args.mode,
        style=args.style,
        width=width,
        height=height,
        seed=args.seed,
        palette_id=args.palette,
        max_colors=args.max_colors,
        frame_duration_ms=args.frame_ms,
        run_qa=args.qa,
        reference_chaining=args.reference_chain,
        check_consistency=args.consistency,
    )

    def on_progress(stage: str, percent: float) -> None:
        print(f"{stage} {percent:.0f}%", file=sys.stderr)

    try:
        result = sequence.generate("cli", request, on_progress)
    except UnknownRegistryKeyError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    payload = result.model_dump()
    payload["gif_path"] = str(output_dir / result.gif_filename)
    payload["sheet_path"] = str(output_dir / result.sheet_filename)
    for frame, meta in zip(payload["frames"], result.frames, strict=True):
        frame["path"] = str(output_dir / meta.filename)
    print(json.dumps(payload, indent=2))
    return 0


def _peak_vram_mb() -> float | None:
    """Peak CUDA memory since process start, in MB — None off CUDA or without torch."""
    try:
        import torch
    except ImportError:
        return None
    if not torch.cuda.is_available():
        return None
    return round(torch.cuda.max_memory_allocated() / (1024 * 1024), 1)


def _cmd_benchmark(args: argparse.Namespace) -> int:
    import tempfile

    from pixelforge.generation.backends.registry import get_backend
    from pixelforge.generation.benchmark import default_suite, run_benchmark
    from pixelforge.models_manager.device import resolve_device

    settings = get_settings()
    backend_name = args.backend or settings.backend
    device = resolve_device(settings.device)
    with tempfile.TemporaryDirectory(prefix="pixelforge-bench-") as tmp:
        outputs_dir = Path(tmp)
        modes = ModeRegistry()
        styles = StyleRegistry(user_dir=settings.user_styles_dir)
        pipeline = GenerationPipeline(
            backend_name=backend_name,
            outputs_dir=outputs_dir,
            modes=modes,
            styles=styles,
            palettes=PaletteService(user_dir=settings.user_palettes_dir),
            diffusion_resolution=settings.diffusion_resolution,
            diffusion_steps=settings.diffusion_steps,
        )
        report = run_benchmark(
            pipeline,
            default_suite(),
            outputs_dir,
            backend=get_backend(backend_name).name,
            device=device,
            peak_vram_mb=_peak_vram_mb(),
        )
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report.model_dump(), indent=2))
    print(json.dumps(report.model_dump(), indent=2))
    return 0


def _cmd_character(args: argparse.Namespace) -> int:
    memory = _character_memory(get_settings())
    if args.character_command == "create":
        character = memory.create(
            args.name,
            CharacterIdentity(
                subject=args.subject,
                proportions=args.proportions,
                silhouette=args.silhouette,
            ),
            palette_id=args.palette,
        )
        payload: object = character.model_dump()
    elif args.character_command == "list":
        payload = [c.model_dump() for c in memory.list()]
    elif args.character_command == "add-frame":
        image = Image.open(args.image).convert("RGBA")
        payload = memory.add_reference_frame(args.character_id, image, args.label).model_dump()
    else:  # drift
        image = Image.open(args.image).convert("RGBA")
        payload = memory.check_drift(args.character_id, image).model_dump()
    print(json.dumps(payload, indent=2))
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
    elif args.what == "plugins":
        payload = load_plugins(settings).model_dump(mode="json")
    elif args.what == "actions":
        from pixelforge.animation.actions import ANIMATION_ACTIONS

        payload = [a.model_dump() for a in ANIMATION_ACTIONS]
    else:
        payload = list_backends()
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_tileset(args: argparse.Namespace) -> int:
    from pixelforge.tileset.service import TileSet, TileSetRequest

    settings = get_settings()
    width, height = _parse_size(args.size)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pipeline = GenerationPipeline(
        backend_name=settings.backend,
        outputs_dir=output_dir,
        modes=ModeRegistry(),
        styles=StyleRegistry(user_dir=settings.user_styles_dir),
        palettes=PaletteService(user_dir=settings.user_palettes_dir),
        diffusion_resolution=settings.diffusion_resolution,
        diffusion_steps=settings.diffusion_steps,
    )
    request = TileSetRequest(
        prompt=args.prompt,
        variants=args.variants,
        mode=args.mode,
        style=args.style,
        width=width,
        height=height,
        seed=args.seed,
        palette_id=args.palette,
        max_colors=args.max_colors,
    )

    def on_progress(stage: str, percent: float) -> None:
        print(f"{stage} {percent:.0f}%", file=sys.stderr)

    result = TileSet(pipeline, output_dir).generate("cli", request, on_progress)
    payload = result.model_dump()
    payload["sheet_path"] = str(output_dir / result.sheet_filename)
    for tile, meta in zip(payload["tiles"], result.tiles, strict=True):
        tile["path"] = str(output_dir / meta.filename)
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_project(args: argparse.Namespace) -> int:
    from pixelforge.projects.bundle import (
        ProjectBundle,
        bundle_info,
        load_bundle,
        save_bundle,
    )

    if args.project_command == "save":
        sprites_dir = Path(args.sprites)
        if not sprites_dir.is_dir():
            print(f"error: not a directory: {sprites_dir}", file=sys.stderr)
            return 2
        images = {p.name: p.read_bytes() for p in sorted(sprites_dir.glob("*.png"))}
        bundle = ProjectBundle(name=args.name, sprites=sorted(images))
        path = save_bundle(bundle, images, Path(args.file))
        print(json.dumps({"saved": str(path), "sprites": len(images)}, indent=2))
        return 0
    if args.project_command == "load":
        loaded = load_bundle(Path(args.file))
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "manifest.json").write_text(
            json.dumps(loaded.bundle.model_dump(), indent=2, sort_keys=True)
        )
        for name, data in loaded.images.items():
            (out_dir / name).write_bytes(data)
        print(json.dumps({"extracted": str(out_dir), "sprites": len(loaded.images)}, indent=2))
        return 0
    # info
    print(json.dumps(bundle_info(Path(args.file)), indent=2))
    return 0


def _cmd_dataset(args: argparse.Namespace) -> int:
    directory = Path(args.directory)
    if not directory.is_dir():
        print(f"error: not a directory: {directory}", file=sys.stderr)
        return 2
    inputs = scan_directory(directory)
    out_dir = Path(args.output_dir) if args.output_dir else None
    report = build_dataset(
        inputs, root=str(directory), out_dir=out_dir, dup_distance=max(0, args.dup_distance)
    )
    print(json.dumps(report.model_dump(), indent=2))
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
    load_plugins(get_settings())  # register plugin components before any command runs
    handlers = {
        "generate": _cmd_generate,
        "plan": _cmd_plan,
        "palette": _cmd_palette,
        "qa": _cmd_qa,
        "benchmark": _cmd_benchmark,
        "animate": _cmd_animate,
        "character": _cmd_character,
        "export": _cmd_export,
        "tileset": _cmd_tileset,
        "project": _cmd_project,
        "dataset": _cmd_dataset,
        "list": _cmd_list,
        "system": _cmd_system,
    }
    try:
        return handlers[args.command](args)
    except (PixelForgeError, ValueError, FileNotFoundError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
