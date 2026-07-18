"""Centralized configuration. Every tunable lives here.

Values can be overridden with environment variables prefixed ``PIXELFORGE_``,
e.g. ``PIXELFORGE_BACKEND=mock`` or ``PIXELFORGE_PORT=9000``.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PIXELFORGE_")

    host: str = "127.0.0.1"
    port: int = 8765

    data_dir: Path = Path.home() / ".pixelforge"
    backend: str = "auto"  # "auto" | "flux-schnell" | "mock"
    device: str = "auto"  # "auto" | "cuda" | "mps" | "cpu"

    flux_model_id: str = "black-forest-labs/FLUX.1-schnell"
    diffusion_resolution: int = 1024
    diffusion_steps: int = 4

    # Agentic planning layer (D-009/D-010). Off by default: the fast path uses prompt_builder and
    # reproduces existing output exactly. When enabled, agents build a Scene Graph that is compiled
    # into the diffusion prompt. ``planning_backend`` selects the provider ("mock" ships in M7).
    planning_enabled: bool = False
    planning_backend: str = "mock"

    # Pixel QA engine (D-013). Off by default. When enabled, generated sprites pass through the QA
    # engine and (if ``qa_autorepair``) its safe deterministic repairs before being saved.
    qa_enabled: bool = False
    qa_autorepair: bool = True
    qa_pass_threshold: float = 0.6

    # Plugin SDK (D-014). Off by default: plugins load only when enabled AND their distribution
    # name is on the explicit allowlist — plugins run in-process with full trust.
    plugins_enabled: bool = False
    plugin_allowlist: list[str] = Field(default_factory=list)

    # Character memory (D-011). Always available (opt-in per request via ``character_id``).
    # ``memory_embedding_backend`` selects the identity-embedding provider ("mock" ships in M10);
    # ``memory_drift_threshold`` is the cosine-similarity gate below which a sprite counts as drift.
    memory_embedding_backend: str = "mock"
    memory_drift_threshold: float = 0.85

    max_queue_size: int = 64
    autosave_interval_seconds: int = 60
    undo_history_limit: int = 100

    @property
    def outputs_dir(self) -> Path:
        return self.data_dir / "outputs"

    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def user_palettes_dir(self) -> Path:
        return self.data_dir / "palettes"

    @property
    def characters_dir(self) -> Path:
        return self.data_dir / "characters"

    @property
    def user_styles_dir(self) -> Path:
        return self.data_dir / "styles"

    def ensure_directories(self) -> None:
        for path in (
            self.outputs_dir,
            self.projects_dir,
            self.models_dir,
            self.user_palettes_dir,
            self.user_styles_dir,
            self.characters_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
