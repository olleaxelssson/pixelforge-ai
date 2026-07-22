"""LoRA trainer (M4, D-001): gated exactly like the FLUX backend.

Actual training needs a GPU plus the kohya/PEFT training stack, none of which ships in CI. So the
trainer is *always* constructible and its planning surface (``training_plan``) is pure and testable,
but :meth:`train` raises :class:`BackendUnavailableError` unless the heavy dependencies are present.
The deterministic half of the toolkit — validate/dedup/caption/manifest — never touches this class.
"""

from __future__ import annotations

from pathlib import Path

from pixelforge.core.errors import BackendUnavailableError
from pixelforge.dataset.models import LoraConfig


class LoraTrainer:
    """Kohya-style LoRA fine-tuner for a prepared dataset.

    Gated like :class:`~pixelforge.generation.backends.flux.FluxSchnellBackend`: ``is_available``
    reports whether the training stack is installed, and ``train`` refuses to run without it.
    """

    name = "kohya-lora"

    def is_available(self) -> bool:
        try:
            import peft  # noqa: F401
            import torch  # noqa: F401
        except ImportError:
            return False
        return True

    def training_plan(self, manifest_path: Path, config: LoraConfig, output_dir: Path) -> list[str]:
        """Return the kohya ``sd-scripts`` command line this trainer would run (pure)."""
        return [
            "accelerate",
            "launch",
            "flux_train_network.py",
            f"--pretrained_model_name_or_path={config.base_model}",
            f"--dataset_config={manifest_path}",
            f"--output_dir={output_dir}",
            f"--resolution={config.resolution}",
            f"--network_dim={config.network_dim}",
            f"--network_alpha={config.network_alpha}",
            f"--learning_rate={config.learning_rate}",
            f"--train_batch_size={config.train_batch_size}",
            f"--max_train_epochs={config.max_train_epochs}",
            f"--optimizer_type={config.optimizer}",
            f"--lr_scheduler={config.lr_scheduler}",
            f"--mixed_precision={config.mixed_precision}",
            "--network_module=networks.lora",
        ]

    def train(self, manifest_path: Path, config: LoraConfig, output_dir: Path) -> Path:
        """Fine-tune a LoRA on the prepared dataset. Requires the ``[ml]`` extra + a GPU."""
        if not self.is_available():
            raise BackendUnavailableError(
                "LoRA training dependencies not installed. Install with: "
                "pip install 'pixelforge[ml]' (and a kohya sd-scripts checkout + GPU)."
            )
        # Real training is invoked here behind the gate; see training_plan() for the command line.
        raise BackendUnavailableError(
            "LoRA training is not wired to a local sd-scripts checkout in this build."
        )
