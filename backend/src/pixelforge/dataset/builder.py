"""Dataset builder (M4, D-001): validate → dedup → caption → training manifest + LoRA config.

Pure and deterministic: given a stable-ordered list of loaded images (a corrupt file is an input
with no image), it produces a :class:`DatasetReport` and, optionally, writes a kohya/HF
``manifest.jsonl`` and a ``lora_config.json``. Near-duplicates are excluded from the manifest.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from pixelforge.dataset.caption import caption_image
from pixelforge.dataset.models import (
    DatasetItem,
    DatasetReport,
    DuplicateCluster,
    LoraConfig,
)
from pixelforge.dataset.phash import (
    DEFAULT_DUP_DISTANCE,
    cluster_duplicates,
    dhash,
    hamming_distance,
)

_MIN_SIZE = 8
_MAX_TRAIN_RES = 512
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}


@dataclass
class LoadedImage:
    name: str
    image: Image.Image | None = None
    load_error: str | None = None


def scan_directory(root: Path) -> list[LoadedImage]:
    """Load every image file under ``root`` (sorted); unreadable files come back with an error."""
    loaded: list[LoadedImage] = []
    for path in sorted(p for p in root.rglob("*") if p.suffix.lower() in _IMAGE_SUFFIXES):
        name = str(path.relative_to(root))
        try:
            image = Image.open(path)
            image.load()
            loaded.append(LoadedImage(name=name, image=image.convert("RGBA")))
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            loaded.append(LoadedImage(name=name, load_error=f"unreadable: {exc}"))
    return loaded


def _validate(loaded: LoadedImage) -> DatasetItem:
    if loaded.image is None:
        return DatasetItem(
            name=loaded.name, valid=False, issues=[loaded.load_error or "corrupt or unreadable"]
        )
    width, height = loaded.image.size
    issues: list[str] = []
    if width < _MIN_SIZE or height < _MIN_SIZE:
        return DatasetItem(
            name=loaded.name, valid=False, width=width, height=height, issues=["smaller than 8px"]
        )
    if width > _MAX_TRAIN_RES or height > _MAX_TRAIN_RES:
        issues.append(f"larger than training resolution ({_MAX_TRAIN_RES}px)")
    if width != height:
        issues.append("non-square")
    return DatasetItem(name=loaded.name, valid=True, width=width, height=height, issues=issues)


def build_dataset(
    inputs: list[LoadedImage],
    root: str = "uploaded",
    out_dir: Path | None = None,
    dup_distance: int = DEFAULT_DUP_DISTANCE,
) -> DatasetReport:
    by_name = {i.name: i for i in inputs}
    items = [_validate(i) for i in inputs]

    # Perceptual hash + caption every valid item, in input order.
    for item in items:
        if not item.valid:
            continue
        image = by_name[item.name].image
        assert image is not None
        item.phash = dhash(image)
        item.caption, item.tags = caption_image(image)

    duplicate_of = cluster_duplicates(
        [(i.name, i.phash) for i in items if i.valid], max_distance=dup_distance
    )
    clusters: dict[str, DuplicateCluster] = {}
    by_item = {i.name: i for i in items}
    for member, representative in duplicate_of.items():
        by_item[member].duplicate_of = representative
        cluster = clusters.setdefault(
            representative, DuplicateCluster(representative=representative)
        )
        cluster.members.append(member)
        cluster.distance = max(
            cluster.distance, hamming_distance(by_item[member].phash, by_item[representative].phash)
        )

    trainable = [i for i in items if i.valid and i.duplicate_of is None]
    manifest = [
        {
            "file_name": i.name,
            "caption": i.caption,
            "tags": i.tags,
            "width": i.width,
            "height": i.height,
        }
        for i in trainable
    ]
    config = LoraConfig(image_count=len(trainable))

    report = DatasetReport(
        root=root,
        total=len(items),
        valid_count=sum(1 for i in items if i.valid),
        invalid_count=sum(1 for i in items if not i.valid),
        duplicate_count=len(duplicate_of),
        items=items,
        clusters=list(clusters.values()),
        lora_config=config,
        manifest=manifest,
    )

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = out_dir / "manifest.jsonl"
        manifest_path.write_text("\n".join(json.dumps(r) for r in manifest) + "\n")
        config_path = out_dir / "lora_config.json"
        config_path.write_text(json.dumps(config.model_dump(), indent=2))
        report.manifest_path = str(manifest_path)
        report.config_path = str(config_path)

    return report
