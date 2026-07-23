"""Local web app: gallery, search, filters, asset detail with analysis + attribution, and an
upload area that both imports and critiques.

A single self-contained FastAPI app. The frontend is one embedded HTML page (no build step) that
talks to a small JSON API. It binds to localhost by default and only ever serves files out of the
configured data directory. Nothing here reaches the network — analysis and search are entirely local.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from studylab.config import Settings
from studylab.db import Database, open_db
from studylab.importer import ImportRequest, import_bytes
from studylab.logging_setup import configure_logging, get_logger

log = get_logger("webapp")


def _asset_summary(db: Database, asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": asset["id"],
        "title": asset["title"],
        "license": asset["license"],
        "creator": asset["creator"],
        "width": asset["width"],
        "height": asset["height"],
        "is_pixel_art": bool(asset["is_pixel_art"]),
        "frame_count": asset["frame_count"],
        "palette_size": asset["palette_size"],
        "grid_scale": asset["grid_scale"],
        "colors": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in db.get_colors(asset["id"])[:6]],
    }


def _asset_detail(db: Database, asset: dict[str, Any]) -> dict[str, Any]:
    aid = int(asset["id"])
    source = db.get_source(asset["source_id"]) if asset["source_id"] else None
    analysis = json.loads(asset["analysis_json"]) if asset.get("analysis_json") else {}
    notes = json.loads(asset["notes_json"]) if asset.get("notes_json") else {}
    from studylab.analysis import rebuild_digest
    from studylab.analysis.critique import critique

    tags = db.get_tags(aid)
    detail = _asset_summary(db, asset)
    detail.update(
        {
            "attribution": asset["attribution"],
            "source_url": asset["source_url"],
            "source_name": source["name"] if source else None,
            "collected_at": asset["collected_at"],
            "format": asset["format"],
            "has_alpha": bool(asset["has_alpha"]),
            "transparent_ratio": asset["transparent_ratio"],
            "tileable_h": asset["tileable_h"],
            "tileable_v": asset["tileable_v"],
            "pixel_art_confidence": asset["pixel_art_confidence"],
            "manual_override": bool(asset["manual_override"]),
            "tags": [{"tag": t["tag"], "origin": t["origin"]} for t in tags],
            "notes": notes.get("notes", []),
            "reads_at": notes.get("reads_at"),
            "analysis": analysis,
            "critique": critique(analysis) if analysis else {},
            "digest": rebuild_digest(analysis, license=asset["license"], tags=[]) if analysis else "",
        }
    )
    return detail


def create_app(settings: Settings) -> FastAPI:
    configure_logging(settings.log_path)
    settings.ensure_dirs()
    app = FastAPI(title="Pixel Art Study Lab", docs_url="/api/docs")

    def db() -> Database:
        return open_db(settings.db_path)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    @app.get("/api/stats")
    def stats() -> dict[str, Any]:
        conn = db()
        try:
            by_license: dict[str, int] = {}
            pixel = 0
            for a in conn.list_assets(limit=1_000_000):
                by_license[a["license"]] = by_license.get(a["license"], 0) + 1
                pixel += int(a["is_pixel_art"])
            return {"assets": conn.count_assets(), "pixel_art": pixel, "by_license": by_license}
        finally:
            conn.close()

    @app.get("/api/assets")
    def assets(
        limit: int = Query(60, le=200),
        offset: int = 0,
        pixel_art: bool = False,
        license: str | None = None,
        tag: str | None = None,
        source_id: int | None = None,
    ) -> dict[str, Any]:
        conn = db()
        try:
            rows = conn.list_assets(
                limit=limit, offset=offset, pixel_art_only=pixel_art,
                license=license, tag=tag, source_id=source_id,
            )
            return {"count": len(rows), "assets": [_asset_summary(conn, a) for a in rows]}
        finally:
            conn.close()

    @app.get("/api/assets/{asset_id}")
    def asset_detail(asset_id: int) -> dict[str, Any]:
        conn = db()
        try:
            asset = conn.get_asset(asset_id)
            if not asset:
                raise HTTPException(404, "asset not found")
            return _asset_detail(conn, asset)
        finally:
            conn.close()

    @app.get("/api/search")
    def search_endpoint(
        q: str | None = None,
        color: str | None = None,
        like: int | None = None,
        tag: str | None = None,
        license: str | None = None,
        pixel_art: bool = False,
        limit: int = 60,
    ) -> dict[str, Any]:
        from studylab.search import Query as SearchQuery
        from studylab.search import search as run_search

        conn = db()
        try:
            color_rgb = _hex_to_rgb(color) if color else None
            query = SearchQuery(
                text=q, color=color_rgb, like_asset_id=like, tag=tag,
                license=license, pixel_art_only=pixel_art, limit=limit,
            )
            hits = run_search(conn, query)
            out = []
            for hit in hits:
                a = conn.get_asset(hit.asset_id)
                if a:
                    summary = _asset_summary(conn, a)
                    summary["score"] = round(hit.score, 3)
                    out.append(summary)
            return {"count": len(out), "assets": out}
        finally:
            conn.close()

    @app.get("/api/similar/{asset_id}")
    def similar(asset_id: int, limit: int = 12) -> dict[str, Any]:
        from studylab.search import search_like_asset

        conn = db()
        try:
            out = []
            for hit in search_like_asset(conn, asset_id, limit=limit):
                a = conn.get_asset(hit.asset_id)
                if a:
                    summary = _asset_summary(conn, a)
                    summary["score"] = round(hit.score, 3)
                    out.append(summary)
            return {"count": len(out), "assets": out}
        finally:
            conn.close()

    @app.post("/api/upload")
    async def upload(
        file: UploadFile = File(...),
        license: str = Form("self"),
        creator: str | None = Form(None),
        title: str | None = Form(None),
        tags: str | None = Form(None),
        override: bool = Form(False),
    ) -> JSONResponse:
        data = await file.read()
        conn = db()
        try:
            import datetime

            source_id = conn.upsert_source(
                name="uploads", kind="local",
                added_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
            req = ImportRequest(
                source_id=source_id, license=license, creator=creator,
                title=title or Path(file.filename or "upload").stem,
                tags=[t.strip() for t in (tags or "").split(",") if t.strip()],
                manual_override=override,
            )
            result = import_bytes(conn, settings, data, req)
            return JSONResponse(
                {"status": result.status, "asset_id": result.asset_id,
                 "message": result.message, "warnings": result.warnings, "digest": result.digest}
            )
        finally:
            conn.close()

    @app.post("/api/critique")
    async def critique_endpoint(file: UploadFile = File(...)) -> dict[str, Any]:
        import io

        from PIL import Image, UnidentifiedImageError

        from studylab.analysis import analyze
        from studylab.analysis.critique import critique
        from studylab.analysis.vlm import describe

        data = await file.read()
        try:
            image = Image.open(io.BytesIO(data))
            image.load()
        except (UnidentifiedImageError, OSError):
            raise HTTPException(400, "not a readable image")
        result = analyze(image)
        vlm = describe(Path(file.filename or "upload"), result.analysis,
                       settings.vlm_provider, settings.vlm_api_key)
        # describe() may attempt an API call only when a provider+key are set; local otherwise.
        return {
            "digest": result.digest,
            "caption": vlm.caption,
            "tags": vlm.tags,
            "vlm_provider": vlm.provider,
            "notes": result.analysis["notes"]["notes"],
            "reads_at": result.analysis["notes"]["reads_at"],
            "critique": critique(result.analysis),
            "analysis": result.analysis,
        }

    @app.delete("/api/assets/{asset_id}")
    def delete_asset(asset_id: int) -> dict[str, Any]:
        conn = db()
        try:
            rel = conn.delete_asset(asset_id)
            if rel:
                for base, name in (
                    (settings.assets_dir, rel),
                    (settings.thumbs_dir, Path(rel).stem + ".png"),
                ):
                    p = base / name
                    if p.exists():
                        p.unlink()
            return {"deleted": asset_id, "file": rel}
        finally:
            conn.close()

    @app.get("/api/thumb/{asset_id}")
    def thumb(asset_id: int) -> FileResponse:
        return _serve(settings, asset_id, thumb=True)

    @app.get("/api/image/{asset_id}")
    def image(asset_id: int) -> FileResponse:
        return _serve(settings, asset_id, thumb=False)

    return app


def _serve(settings: Settings, asset_id: int, *, thumb: bool) -> FileResponse:
    conn = open_db(settings.db_path)
    try:
        asset = conn.get_asset(asset_id)
        if not asset:
            raise HTTPException(404, "asset not found")
        if thumb and asset["thumb_path"]:
            path = settings.thumbs_dir / asset["thumb_path"]
        else:
            path = settings.assets_dir / asset["file_path"]
        if not path.exists():
            raise HTTPException(404, "file missing")
        return FileResponse(path)
    finally:
        conn.close()


def _hex_to_rgb(text: str) -> tuple[int, int, int]:
    t = text.strip().lstrip("#")
    if len(t) == 6:
        return (int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16))
    parts = [int(p) for p in t.replace(",", " ").split()]
    return (parts[0], parts[1], parts[2])


INDEX_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Pixel Art Study Lab</title>
<style>
  :root { --bg:#12131c; --panel:#1c1e2b; --line:#2c2f42; --fg:#e7e8f0; --muted:#9aa0b6;
          --accent:#7c9cff; --good:#6ee7a8; --warn:#ffcd75; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font:14px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
  header { padding:14px 20px; border-bottom:1px solid var(--line); display:flex; gap:14px;
           align-items:center; position:sticky; top:0; background:var(--bg); z-index:5; flex-wrap:wrap; }
  h1 { font-size:16px; margin:0; letter-spacing:.3px; }
  h1 span { color:var(--accent); }
  input, select, button { background:var(--panel); color:var(--fg); border:1px solid var(--line);
           border-radius:8px; padding:7px 10px; font:inherit; }
  button { cursor:pointer; } button:hover { border-color:var(--accent); }
  #search { flex:1; min-width:180px; }
  .pill { color:var(--muted); font-size:12px; }
  main { display:grid; grid-template-columns:1fr; gap:0; }
  #gallery { display:grid; grid-template-columns:repeat(auto-fill,minmax(120px,1fr));
             gap:12px; padding:20px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:10px; overflow:hidden;
          cursor:pointer; transition:transform .08s, border-color .08s; }
  .card:hover { transform:translateY(-2px); border-color:var(--accent); }
  .card .img { aspect-ratio:1; display:flex; align-items:center; justify-content:center;
               background:repeating-conic-gradient(#0000 0 25%, #ffffff0a 0 50%) 0 0/16px 16px, #0d0e16; }
  .card img { image-rendering:pixelated; max-width:100%; max-height:100%; }
  .card .meta { padding:6px 8px; font-size:11px; color:var(--muted);
                white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .swatches { display:flex; height:6px; } .swatches i { flex:1; }
  #drawer { position:fixed; top:0; right:0; height:100%; width:min(460px,92vw); background:var(--panel);
            border-left:1px solid var(--line); transform:translateX(100%); transition:transform .18s;
            overflow-y:auto; z-index:10; padding:20px; }
  #drawer.open { transform:none; }
  #drawer img { image-rendering:pixelated; max-width:100%; background:#0d0e16; border-radius:8px; }
  .row { display:flex; justify-content:space-between; gap:8px; padding:4px 0; border-bottom:1px dashed var(--line); }
  .row b { color:var(--muted); font-weight:500; }
  .tag { display:inline-block; background:#2a2d40; border-radius:6px; padding:2px 7px; margin:2px; font-size:11px; }
  .tag.auto { color:var(--muted); } .tag.user { color:var(--good); }
  .note { padding:6px 10px; border-left:2px solid var(--accent); margin:6px 0; color:#cdd2e6; }
  .sug { border-left-color:var(--warn); } .warnbox { color:var(--warn); }
  .digest { font-family:ui-monospace,monospace; font-size:11px; white-space:pre-wrap; word-break:break-all;
            background:#0d0e16; padding:8px; border-radius:8px; color:#a7b0d0; }
  #uploadPanel { padding:16px 20px; border-bottom:1px solid var(--line); display:none; gap:10px; flex-wrap:wrap; align-items:center; }
  #uploadPanel.open { display:flex; }
  #dropzone { border:1.5px dashed var(--line); border-radius:10px; padding:14px 18px; color:var(--muted); }
  .close { float:right; }
  .empty { padding:40px; color:var(--muted); text-align:center; }
  a { color:var(--accent); }
</style></head>
<body>
<header>
  <h1>Pixel Art <span>Study Lab</span></h1>
  <input id="search" placeholder="Search title, tags, notes, creator… (blank = browse)"/>
  <input id="color" type="color" title="search by colour" value="#7c9cff"/>
  <button id="colorBtn">By colour</button>
  <select id="license"><option value="">any license</option></select>
  <label class="pill"><input type="checkbox" id="pxonly"/> pixel-art only</label>
  <button id="toggleUpload">Upload / Critique</button>
  <span class="pill" id="stat"></span>
</header>
<div id="uploadPanel">
  <div id="dropzone">Drop an image here, or
    <input type="file" id="file" accept="image/*"/></div>
  <select id="upLicense">
    <option value="self">self (my own)</option>
    <option value="CC0-1.0">CC0-1.0</option><option value="PD">PD</option>
    <option value="CC-BY-4.0">CC-BY-4.0</option><option value="CC-BY-SA-4.0">CC-BY-SA-4.0</option>
  </select>
  <input id="upCreator" placeholder="creator (optional)"/>
  <input id="upTags" placeholder="tags, comma-separated"/>
  <button id="importBtn">Import to library</button>
  <button id="critiqueBtn">Critique only</button>
  <span class="pill" id="upMsg"></span>
</div>
<main><div id="gallery"></div></main>
<div id="drawer"></div>

<script>
const $ = s => document.querySelector(s);
const gallery = $('#gallery'), drawer = $('#drawer');
async function j(u,o){ const r = await fetch(u,o); if(!r.ok) throw new Error(await r.text()); return r.json(); }

async function loadStats(){
  const s = await j('/api/stats');
  $('#stat').textContent = `${s.assets} assets · ${s.pixel_art} pixel-art`;
  const sel = $('#license'); sel.length = 1;
  Object.keys(s.by_license).sort().forEach(l => { const o=document.createElement('option'); o.value=o.textContent=l; sel.appendChild(o); });
}
function card(a){
  const el = document.createElement('div'); el.className='card'; el.onclick=()=>openAsset(a.id);
  const sw = (a.colors||[]).map(c=>`<i style="background:${c}"></i>`).join('');
  el.innerHTML = `<div class="img"><img loading="lazy" src="/api/thumb/${a.id}"/></div>
    <div class="swatches">${sw}</div>
    <div class="meta">${a.title||'untitled'} · ${a.width}×${a.height}${a.score!=null?' · '+a.score:''}</div>`;
  return el;
}
function render(list){
  gallery.innerHTML='';
  if(!list.length){ gallery.innerHTML='<div class="empty">Nothing here yet. Try <code>studylab demo</code>, or upload an image above.</div>'; return; }
  list.forEach(a=>gallery.appendChild(card(a)));
}
async function browse(){
  const p = new URLSearchParams();
  const q=$('#search').value.trim();
  if($('#pxonly').checked) p.set('pixel_art','true');
  if($('#license').value) p.set('license',$('#license').value);
  let url;
  if(q){ p.set('q',q); url='/api/search?'+p; }
  else { url='/api/assets?'+p; }
  render((await j(url)).assets);
}
async function byColor(){
  const p = new URLSearchParams({color:$('#color').value});
  if($('#pxonly').checked) p.set('pixel_art','true');
  render((await j('/api/search?'+p)).assets);
}
async function openAsset(id){
  const a = await j('/api/assets/'+id);
  const rows = [['license',a.license],['creator',a.creator||'—'],['size',a.width+'×'+a.height],
    ['grid',a.grid_scale+'px'],['palette',a.palette_size+' colours'],['frames',a.frame_count],
    ['pixel-art',a.is_pixel_art?('yes ('+(a.pixel_art_confidence*100|0)+'%)'):'no'],
    ['tileable','H '+(a.tileable_h*100|0)+'% · V '+(a.tileable_v*100|0)+'%'],
    ['transparent',(a.transparent_ratio*100|0)+'%'],['collected',a.collected_at||'—']];
  const tags = (a.tags||[]).map(t=>`<span class="tag ${t.origin}">${t.tag}</span>`).join('')||'<span class="pill">no tags</span>';
  const notes = (a.notes||[]).map(n=>`<div class="note">${n}</div>`).join('');
  const strengths = ((a.critique||{}).strengths||[]).map(s=>`<div class="note">${s}</div>`).join('');
  const sugg = ((a.critique||{}).suggestions||[]).map(s=>`<div class="note sug">${s}</div>`).join('');
  drawer.innerHTML = `<button class="close" onclick="drawer.classList.remove('open')">✕ close</button>
    <h2 style="margin-top:0">${a.title||'untitled'}</h2>
    <img src="/api/image/${a.id}"/>
    <p class="pill">${a.reads_at||''}</p>
    ${rows.map(r=>`<div class="row"><b>${r[0]}</b><span>${r[1]}</span></div>`).join('')}
    ${a.attribution?`<div class="row"><b>attribution</b><span>${a.attribution}</span></div>`:''}
    ${a.source_url?`<div class="row"><b>source</b><a href="${a.source_url}" target="_blank" rel="noopener">link</a></div>`:''}
    <h3>Tags</h3>${tags}
    <h3>Why it reads</h3>${notes||'<span class="pill">—</span>'}
    <h3>Study critique</h3>${strengths}${sugg}
    <h3>LLM digest</h3><div class="digest">${a.digest||''}</div>
    <div style="margin-top:14px"><button onclick="showSimilar(${a.id})">Find similar</button>
      <button onclick="delAsset(${a.id})" style="color:#ff8a8a">Remove</button></div>
    <div id="similar"></div>`;
  drawer.classList.add('open');
}
async function showSimilar(id){
  const s = await j('/api/similar/'+id);
  $('#similar').innerHTML = '<h3>Similar</h3>' + (s.assets.length?'':'<span class="pill">none</span>');
  const box = document.createElement('div'); box.style.display='grid';
  box.style.gridTemplateColumns='repeat(4,1fr)'; box.style.gap='8px';
  s.assets.forEach(a=>box.appendChild(card(a))); $('#similar').appendChild(box);
}
async function delAsset(id){
  if(!confirm('Remove this asset and its files?')) return;
  await j('/api/assets/'+id,{method:'DELETE'}); drawer.classList.remove('open'); browse(); loadStats();
}
async function doUpload(critiqueOnly){
  const f = $('#file').files[0]; if(!f){ $('#upMsg').textContent='choose a file first'; return; }
  const fd = new FormData(); fd.append('file', f);
  if(critiqueOnly){
    const r = await j('/api/critique',{method:'POST',body:fd});
    drawer.innerHTML = `<button class="close" onclick="drawer.classList.remove('open')">✕ close</button>
      <h2 style="margin-top:0">Critique</h2><p class="pill">${r.reads_at}</p>
      <div class="digest">${r.digest}</div>
      <h3>Caption</h3><p>${r.caption} <span class="pill">(${r.vlm_provider})</span></p>
      <h3>Why it reads</h3>${r.notes.map(n=>`<div class="note">${n}</div>`).join('')}
      <h3>Strengths</h3>${r.critique.strengths.map(s=>`<div class="note">${s}</div>`).join('')}
      <h3>Suggestions</h3>${r.critique.suggestions.map(s=>`<div class="note sug">${s}</div>`).join('')}`;
    drawer.classList.add('open'); return;
  }
  fd.append('license',$('#upLicense').value); fd.append('creator',$('#upCreator').value);
  fd.append('tags',$('#upTags').value);
  const r = await j('/api/upload',{method:'POST',body:fd});
  const w = r.warnings&&r.warnings.length ? ` · ⚠ ${r.warnings.length} possible near-duplicate(s)` : '';
  $('#upMsg').innerHTML = `<span class="${r.warnings&&r.warnings.length?'warnbox':''}">${r.status}${w}</span>`;
  browse(); loadStats();
}
$('#search').addEventListener('keydown',e=>{ if(e.key==='Enter') browse(); });
$('#license').onchange=browse; $('#pxonly').onchange=browse;
$('#colorBtn').onclick=byColor;
$('#toggleUpload').onclick=()=>$('#uploadPanel').classList.toggle('open');
$('#importBtn').onclick=()=>doUpload(false); $('#critiqueBtn').onclick=()=>doUpload(true);
const dz=$('#dropzone');
dz.addEventListener('dragover',e=>{e.preventDefault();dz.style.borderColor='var(--accent)';});
dz.addEventListener('dragleave',()=>dz.style.borderColor='');
dz.addEventListener('drop',e=>{e.preventDefault();dz.style.borderColor='';$('#file').files=e.dataTransfer.files;});
loadStats(); browse();
</script>
</body></html>"""
