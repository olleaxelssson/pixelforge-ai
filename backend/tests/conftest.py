import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("PIXELFORGE_BACKEND", "mock")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PIXELFORGE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PIXELFORGE_BACKEND", "mock")
    monkeypatch.setenv("PIXELFORGE_DIFFUSION_RESOLUTION", "128")
    from pixelforge.config import get_settings

    get_settings.cache_clear()
    from pixelforge.main import app

    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()
