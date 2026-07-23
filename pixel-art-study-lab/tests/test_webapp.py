"""Web API: gallery, detail, search, upload, critique, delete — via an in-process test client."""

from __future__ import annotations

from fastapi.testclient import TestClient

from studylab.config import Settings
from studylab.db import open_db
from studylab.importer import ImportRequest, import_bytes
from studylab.webapp import create_app

from .conftest import sprite_png


def _client_with_asset(settings: Settings) -> tuple[TestClient, int]:
    db = open_db(settings.db_path)
    source = db.upsert_source(name="local", kind="local", added_at="2026-01-01T00:00:00")
    res = import_bytes(
        db, settings, sprite_png(1),
        ImportRequest(source_id=source, license="CC0-1.0", creator="Me", title="hero",
                      tags=["knight"]),
    )
    db.close()
    return TestClient(create_app(settings)), res.asset_id or 0


def test_index_and_stats(settings: Settings) -> None:
    client, _ = _client_with_asset(settings)
    assert "Study Lab" in client.get("/").text
    stats = client.get("/api/stats").json()
    assert stats["assets"] == 1


def test_gallery_and_detail(settings: Settings) -> None:
    client, aid = _client_with_asset(settings)
    listing = client.get("/api/assets").json()
    assert listing["count"] == 1
    detail = client.get(f"/api/assets/{aid}").json()
    assert detail["license"] == "CC0-1.0"
    assert detail["attribution"]
    assert detail["digest"].startswith("PALAB/1")
    assert detail["critique"]["strengths"]


def test_search_by_tag(settings: Settings) -> None:
    client, aid = _client_with_asset(settings)
    hits = client.get("/api/search", params={"q": "knight"}).json()
    assert aid in [a["id"] for a in hits["assets"]]


def test_thumb_and_image_served(settings: Settings) -> None:
    client, aid = _client_with_asset(settings)
    assert client.get(f"/api/thumb/{aid}").status_code == 200
    assert client.get(f"/api/image/{aid}").headers["content-type"].startswith("image/")


def test_upload_and_critique(settings: Settings) -> None:
    client, _ = _client_with_asset(settings)
    files = {"file": ("mine.png", sprite_png(50), "image/png")}
    up = client.post("/api/upload", files=files, data={"license": "self", "tags": "test"})
    assert up.json()["status"] == "imported"

    crit = client.post("/api/critique", files={"file": ("c.png", sprite_png(51), "image/png")})
    body = crit.json()
    assert body["digest"].startswith("PALAB/1")
    assert body["critique"]["strengths"]


def test_delete_asset_removes_file(settings: Settings) -> None:
    client, aid = _client_with_asset(settings)
    assert client.delete(f"/api/assets/{aid}").json()["deleted"] == aid
    assert client.get(f"/api/assets/{aid}").status_code == 404


def test_upload_duplicate_is_flagged(settings: Settings) -> None:
    client, _ = _client_with_asset(settings)
    data = sprite_png(77)
    first = client.post("/api/upload", files={"file": ("a.png", data, "image/png")},
                        data={"license": "self"}).json()
    assert first["status"] == "imported"
    second = client.post("/api/upload", files={"file": ("a.png", data, "image/png")},
                         data={"license": "self"}).json()
    assert second["status"] == "duplicate"
