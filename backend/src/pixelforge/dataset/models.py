"""Dataset toolkit data models (M4, D-001)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DatasetItem(BaseModel):
    name: str
    valid: bool
    width: int = 0
    height: int = 0
    issues: list[str] = Field(default_factory=list)
    phash: str = ""  # 16-hex-char perceptual hash (empty when invalid)
    caption: str = ""
    tags: list[str] = Field(default_factory=list)
    duplicate_of: str | None = (
        None  # the cluster's representative, if this item is a near-duplicate
    )


class DuplicateCluster(BaseModel):
    representative: str  # the first item (kept for training)
    members: list[str] = Field(default_factory=list)  # near-duplicates of the representative
    distance: int = 0  # max Hamming distance within the cluster


class LoraConfig(BaseModel):
    """kohya-style LoRA training config; deterministic defaults derived from the dataset."""

    base_model: str = "black-forest-labs/FLUX.1-schnell"
    resolution: int = 512
    network_dim: int = 16
    network_alpha: int = 8
    learning_rate: float = 1e-4
    train_batch_size: int = 2
    max_train_epochs: int = 10
    optimizer: str = "AdamW8bit"
    lr_scheduler: str = "cosine"
    mixed_precision: str = "bf16"
    trigger_word: str = "pixelforge_style"
    image_count: int = 0


class DatasetReport(BaseModel):
    root: str
    total: int
    valid_count: int
    invalid_count: int
    duplicate_count: int
    items: list[DatasetItem] = Field(default_factory=list)
    clusters: list[DuplicateCluster] = Field(default_factory=list)
    lora_config: LoraConfig
    manifest: list[dict[str, object]] = Field(default_factory=list)  # kohya/HF JSONL records
    manifest_path: str | None = None
    config_path: str | None = None
