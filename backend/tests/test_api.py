import time


def _wait_for_job(client, job_id, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("completed", "failed", "cancelled"):
            return job
        time.sleep(0.1)
    raise TimeoutError(f"job {job_id} did not finish")


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_catalogs(client):
    assert len(client.get("/api/modes").json()) == 15
    assert len(client.get("/api/styles").json()) == 12
    assert len(client.get("/api/animations").json()) == 13
    assert len(client.get("/api/palettes").json()) >= 6
    system = client.get("/api/system").json()
    assert 16 in system["supported_sizes"]


def test_generate_end_to_end(client):
    response = client.post(
        "/api/generate",
        json={"prompt": "a brave knight", "width": 32, "height": 32, "seed": 5},
    )
    assert response.status_code == 202
    job = _wait_for_job(client, response.json()["id"])
    assert job["status"] == "completed"
    filename = job["result"]["images"][0]["filename"]
    image = client.get(f"/api/images/{filename}")
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"


def test_generate_rejects_unknown_style(client):
    response = client.post("/api/generate", json={"prompt": "x", "style": "nope"})
    assert response.status_code == 422


def test_cancel_job(client):
    response = client.post("/api/generate", json={"prompt": "y", "batch_size": 4})
    job_id = response.json()["id"]
    client.post(f"/api/jobs/{job_id}/cancel")
    job = _wait_for_job(client, job_id)
    assert job["status"] in ("cancelled", "completed")


def test_export_flow(client):
    response = client.post(
        "/api/generate", json={"prompt": "gem", "width": 16, "height": 16, "seed": 9}
    )
    job = _wait_for_job(client, response.json()["id"])
    filename = job["result"]["images"][0]["filename"]
    export = client.post(
        "/api/export",
        json={"format_id": "png", "filenames": [filename], "options": {"scale": 2}},
    )
    assert export.status_code == 200
    assert export.headers["content-type"] == "image/png"

    unity = client.post("/api/export", json={"format_id": "unity", "filenames": [filename]})
    assert unity.headers["content-type"] == "application/zip"


def test_projects_crud(client):
    project = {"name": "My Game"}
    saved = client.post("/api/projects", json=project).json()
    assert saved["name"] == "My Game"
    assert client.get(f"/api/projects/{saved['id']}").status_code == 200
    assert client.get("/api/projects/latest").json()["id"] == saved["id"]
    assert client.delete(f"/api/projects/{saved['id']}").json()["deleted"]


def test_palette_extract(client):
    import base64
    import io

    from PIL import Image

    image = Image.new("RGB", (8, 8), (255, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    data = base64.b64encode(buffer.getvalue()).decode()
    response = client.post("/api/palettes/extract", json={"image_base64": data})
    assert response.status_code == 200
    assert len(response.json()["colors"]) >= 1
