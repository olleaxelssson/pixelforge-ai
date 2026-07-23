"""``studylab`` command-line interface.

Human-readable by default, ``--json`` for machine output (and every analysis carries the compact
LLM-facing digest). Subcommands: ``init``, ``import``, ``analyze``, ``critique``, ``search``,
``tag``, ``scrape``, ``sources``, ``demo``, ``export``, ``import-dataset``, ``backup``, ``restore``,
``remove``, ``stats``, ``serve``.

Progress and logs go to stderr; results go to stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from studylab.config import Settings, load_settings
from studylab.db import Database, open_db
from studylab.logging_setup import configure_logging


def _out(obj: Any, as_json: bool) -> None:
    if as_json:
        json.dump(obj, sys.stdout, ensure_ascii=False, indent=2, default=str)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(str(obj) + "\n")


def _open(settings: Settings) -> Database:
    settings.ensure_dirs()
    return open_db(settings.db_path)


def _local_source_id(db: Database) -> int:
    import datetime

    return db.upsert_source(
        name="local",
        kind="local",
        added_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    )


# --- commands ---------------------------------------------------------------


def cmd_init(args: argparse.Namespace, settings: Settings) -> int:
    db = _open(settings)
    _local_source_id(db)
    db.close()
    _out({"data_dir": str(settings.data_dir), "db": str(settings.db_path)}, args.json)
    return 0


def cmd_import(args: argparse.Namespace, settings: Settings) -> int:
    from studylab.importer import ImportRequest, import_file, import_folder

    db = _open(settings)
    source_id = _local_source_id(db)
    path = Path(args.path).expanduser()
    results = []
    if path.is_dir():
        results = import_folder(
            db, settings, path,
            source_id=source_id, license=args.license, creator=args.creator,
            recursive=args.recursive, tags=args.tags or [],
        )
    elif path.is_file():
        req = ImportRequest(
            source_id=source_id, license=args.license, creator=args.creator,
            title=args.title or path.stem, source_url=path.as_uri(), tags=args.tags or [],
            require_pixel_art=args.require_pixel_art, manual_override=args.override,
        )
        results = [import_file(db, settings, path, req)]
    else:
        print(f"error: no such file or directory: {path}", file=sys.stderr)
        return 2
    db.close()
    tally: dict[str, int] = {}
    for r in results:
        tally[r.status] = tally.get(r.status, 0) + 1
    payload = {
        "summary": tally,
        "results": [
            {"status": r.status, "asset_id": r.asset_id, "message": r.message,
             "warnings": r.warnings, "digest": r.digest}
            for r in results
        ],
    }
    if args.json:
        _out(payload, True)
    else:
        for r in results:
            warn = f"  ⚠ {len(r.warnings)} near-dup" if r.warnings else ""
            print(f"[{r.status}] {r.message} (asset {r.asset_id}){warn}")
        print(f"\n{tally}")
    return 0


def cmd_analyze(args: argparse.Namespace, settings: Settings) -> int:
    from PIL import Image

    from studylab.analysis import analyze
    from studylab.analysis.critique import critique
    from studylab.analysis.vlm import describe

    path = Path(args.path).expanduser()
    image = Image.open(path)
    image.load()
    result = analyze(image)
    vlm = describe(path, result.analysis, settings.vlm_provider, settings.vlm_api_key)
    payload = {
        "digest": result.digest,
        "caption": vlm.caption,
        "vlm_provider": vlm.provider,
        "tags": vlm.tags,
        "analysis": result.analysis,
        "critique": critique(result.analysis),
    }
    if args.json:
        _out(payload, True)
    else:
        print(result.digest)
        print("\ncaption:", vlm.caption)
        print("notes:")
        for n in result.analysis["notes"]["notes"]:
            print("  -", n)
    return 0


def cmd_critique(args: argparse.Namespace, settings: Settings) -> int:
    from PIL import Image

    from studylab.analysis import analyze
    from studylab.analysis.critique import critique

    image = Image.open(Path(args.path).expanduser())
    image.load()
    result = analyze(image)
    crit = critique(result.analysis)
    payload = {"digest": result.digest, "critique": crit}
    if args.json:
        _out(payload, True)
    else:
        print("STRENGTHS:")
        for s in crit["strengths"]:
            print("  +", s)
        print("SUGGESTIONS:")
        for s in crit["suggestions"]:
            print("  →", s)
    return 0


def cmd_search(args: argparse.Namespace, settings: Settings) -> int:
    from studylab.search import Query, search

    db = _open(settings)
    color = _parse_color(args.color) if args.color else None
    q = Query(
        text=args.text, color=color, like_asset_id=args.like, tag=args.tag,
        license=args.license, pixel_art_only=args.pixel_art, limit=args.limit,
    )
    hits = search(db, q)
    rows = []
    for hit in hits:
        a = db.get_asset(hit.asset_id)
        if a:
            rows.append({"id": a["id"], "title": a["title"], "license": a["license"],
                         "score": round(hit.score, 3), "file": a["file_path"]})
    db.close()
    if args.json:
        _out({"count": len(rows), "results": rows}, True)
    else:
        for r in rows:
            print(f"{r['id']:>5}  {r['score']:.3f}  {r['license']:<12} {r['title']}")
        print(f"\n{len(rows)} result(s)")
    return 0


def cmd_tag(args: argparse.Namespace, settings: Settings) -> int:
    from PIL import Image

    from studylab.analysis import analyze
    from studylab.tagger import TagModel

    db = _open(settings)
    model_path = settings.data_dir / "tagger.npz"
    if args.train:
        model = TagModel.fit(db)
        model.save(model_path)
        db.close()
        _out({"trained_on": model.size, "saved": str(model_path)}, args.json)
        return 0
    if not model_path.exists():
        model = TagModel.fit(db)
    else:
        model = TagModel.load(model_path)
    if not args.path:
        print("error: provide an image path, or use --train", file=sys.stderr)
        db.close()
        return 2
    image = Image.open(Path(args.path).expanduser())
    image.load()
    result = analyze(image)
    suggestions = model.suggest(result.embedding)
    db.close()
    _out({"model_size": model.size,
          "suggestions": [{"tag": s.tag, "score": s.score} for s in suggestions]}, args.json) \
        if args.json else _print_tags(model.size, suggestions)
    return 0


def _print_tags(model_size: int, suggestions: list[Any]) -> None:
    print(f"(tagger trained on {model_size} labelled examples)")
    for s in suggestions:
        print(f"  {s.score:.2f}  {s.tag}")
    if not suggestions:
        print("  (no confident tags — tag a few assets first, then `studylab tag --train`)")


def cmd_scrape(args: argparse.Namespace, settings: Settings) -> int:
    from studylab.scraper.allowlist import find_source, load_allowlist
    from studylab.scraper.runner import RunOptions, run_source

    config_path = Path(args.config).expanduser()
    sources = load_allowlist(config_path)
    if args.list or not args.source:
        payload = [
            {"name": s.name, "adapter": s.adapter, "enabled": s.enabled,
             "licenses": s.allowed_licenses, "queries": s.queries, "urls": len(s.urls)}
            for s in sources
        ]
        if args.json:
            _out(payload, True)
        else:
            if not sources:
                print(f"no sources configured (create {config_path} from sources.example.toml)")
            for s in payload:
                mark = "●" if s["enabled"] else "○"
                print(f"{mark} {s['name']:<24} {s['adapter']:<10} {','.join(s['licenses'])}")
        return 0

    source = find_source(sources, args.source)
    if not source:
        print(f"error: source '{args.source}' not found in {config_path}", file=sys.stderr)
        return 2
    if not source.enabled:
        print(f"error: source '{args.source}' is not enabled (set enabled = true in {config_path})",
              file=sys.stderr)
        return 2

    db = _open(settings)
    options = RunOptions(dry_run=not args.execute, limit=args.limit)
    report = run_source(db, settings, source, options=options)
    db.close()
    payload = {
        "source": report.source, "dry_run": report.dry_run, "counts": report.counts(),
        "outcomes": [
            {"status": o.status, "license": o.license, "title": o.title,
             "url": o.download_url, "message": o.message, "asset_id": o.asset_id}
            for o in report.outcomes
        ],
    }
    if args.json:
        _out(payload, True)
    else:
        mode = "DRY-RUN (nothing downloaded)" if report.dry_run else "COLLECT"
        print(f"{mode} — source '{report.source}': {report.counts()}")
        for o in report.outcomes:
            print(f"  [{o.status}] {o.title or o.download_url} — {o.message}")
        if report.dry_run:
            print("\nre-run with --execute to actually download the 'planned' items.")
    return 0


def cmd_sources(args: argparse.Namespace, settings: Settings) -> int:
    db = _open(settings)
    rows = db.list_sources()
    counts = {int(r["id"]): 0 for r in rows}
    for a in db.list_assets(limit=1_000_000):
        sid = a["source_id"]
        if sid in counts:
            counts[sid] += 1
    db.close()
    payload = [{"id": r["id"], "name": r["name"], "kind": r["kind"], "assets": counts[r["id"]]}
               for r in rows]
    if args.json:
        _out(payload, True)
    else:
        for r in payload:
            print(f"{r['id']:>3}  {r['name']:<24} {r['kind']:<8} {r['assets']} asset(s)")
    return 0


def cmd_demo(args: argparse.Namespace, settings: Settings) -> int:
    from studylab.demo import CREATOR, LICENSE, generate_demo
    from studylab.importer import import_folder

    out_dir = Path(args.dir).expanduser() if args.dir else settings.data_dir / "demo"
    paths = generate_demo(out_dir)
    if args.no_import:
        _out({"generated": [str(p) for p in paths]}, args.json)
        return 0
    db = _open(settings)
    import datetime

    source_id = db.upsert_source(
        name="demo", kind="local",
        license_default=LICENSE, added_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )
    results = import_folder(db, settings, out_dir, source_id=source_id,
                            license=LICENSE, creator=CREATOR, recursive=False)
    db.close()
    tally: dict[str, int] = {}
    for r in results:
        tally[r.status] = tally.get(r.status, 0) + 1
    _out({"generated": len(paths), "imported": tally}, args.json) if args.json else \
        print(f"generated {len(paths)} demo files → imported {tally}")
    return 0


def cmd_export(args: argparse.Namespace, settings: Settings) -> int:
    from studylab.backup import export_dataset

    db = _open(settings)
    path = export_dataset(db, settings, Path(args.out).expanduser())
    db.close()
    _out({"exported": str(path)}, args.json) if args.json else print(f"exported → {path}")
    return 0


def cmd_import_dataset(args: argparse.Namespace, settings: Settings) -> int:
    from studylab.backup import import_dataset

    db = _open(settings)
    summary = import_dataset(db, settings, Path(args.zip).expanduser())
    db.close()
    payload = {"imported": summary.imported, "duplicate": summary.duplicate,
               "refused": summary.refused, "skipped": summary.skipped}
    _out(payload, args.json) if args.json else print(payload)
    return 0


def cmd_backup(args: argparse.Namespace, settings: Settings) -> int:
    from studylab.backup import backup

    path = backup(settings, Path(args.out).expanduser())
    _out({"backup": str(path)}, args.json) if args.json else print(f"backup → {path}")
    return 0


def cmd_restore(args: argparse.Namespace, settings: Settings) -> int:
    from studylab.backup import restore

    restore(settings, Path(args.zip).expanduser())
    _out({"restored": str(settings.data_dir)}, args.json) if args.json else \
        print(f"restored → {settings.data_dir}")
    return 0


def cmd_remove(args: argparse.Namespace, settings: Settings) -> int:
    db = _open(settings)
    removed_files: list[str] = []
    if args.asset is not None:
        path = db.delete_asset(args.asset)
        if path:
            removed_files.append(path)
    elif args.source is not None:
        removed_files.extend(db.delete_source(args.source))
    else:
        print("error: specify --asset <id> or --source <id>", file=sys.stderr)
        db.close()
        return 2
    db.close()
    for rel in removed_files:
        for base in (settings.assets_dir, settings.thumbs_dir):
            for candidate in (base / rel, base / (Path(rel).stem + ".png")):
                if candidate.exists():
                    candidate.unlink()
    _out({"removed_files": len(removed_files)}, args.json) if args.json else \
        print(f"removed {len(removed_files)} file(s)")
    return 0


def cmd_stats(args: argparse.Namespace, settings: Settings) -> int:
    db = _open(settings)
    total = db.count_assets()
    by_license: dict[str, int] = {}
    pixel = 0
    for a in db.list_assets(limit=1_000_000):
        by_license[a["license"]] = by_license.get(a["license"], 0) + 1
        pixel += int(a["is_pixel_art"])
    db.close()
    payload = {"assets": total, "pixel_art": pixel, "by_license": by_license,
               "data_dir": str(settings.data_dir)}
    if args.json:
        _out(payload, True)
    else:
        print(f"assets: {total} ({pixel} pixel-art)")
        for lic, n in sorted(by_license.items()):
            print(f"  {lic:<14} {n}")
    return 0


def cmd_serve(args: argparse.Namespace, settings: Settings) -> int:
    import uvicorn

    from studylab.webapp import create_app

    app = create_app(settings)
    print(f"serving Pixel Art Study Lab on http://{args.host}:{args.port}", file=sys.stderr)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


# --- argument parsing -------------------------------------------------------


def _parse_color(text: str) -> tuple[int, int, int]:
    t = text.strip().lstrip("#")
    if len(t) == 6:
        return (int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16))
    parts = [int(p) for p in t.replace(",", " ").split()]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("color must be #RRGGBB or 'r,g,b'")
    return (parts[0], parts[1], parts[2])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="studylab", description="Local-first pixel-art study lab.")
    p.add_argument("--json", action="store_true", help="machine-readable JSON output")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the data directory and database")

    imp = sub.add_parser("import", help="import a file or folder")
    imp.add_argument("path")
    imp.add_argument("--license", default="self")
    imp.add_argument("--creator")
    imp.add_argument("--title")
    imp.add_argument("--tags", nargs="*")
    imp.add_argument("--recursive", action="store_true", default=True)
    imp.add_argument("--no-recursive", dest="recursive", action="store_false")
    imp.add_argument("--require-pixel-art", action="store_true")
    imp.add_argument("--override", action="store_true", help="force is-pixel-art")

    an = sub.add_parser("analyze", help="analyze an image (no import)")
    an.add_argument("path")

    cr = sub.add_parser("critique", help="critique an image with study feedback")
    cr.add_argument("path")

    se = sub.add_parser("search", help="search the library")
    se.add_argument("text", nargs="?")
    se.add_argument("--color", help="#RRGGBB or 'r,g,b'")
    se.add_argument("--like", type=int, help="asset id to find similar to")
    se.add_argument("--tag")
    se.add_argument("--license")
    se.add_argument("--pixel-art", action="store_true")
    se.add_argument("--limit", type=int, default=30)

    tg = sub.add_parser("tag", help="suggest tags for an image / train the tagger")
    tg.add_argument("path", nargs="?")
    tg.add_argument("--train", action="store_true", help="(re)train from labelled assets")

    sc = sub.add_parser("scrape", help="run a configured source (dry-run by default)")
    sc.add_argument("source", nargs="?")
    sc.add_argument("--config", default="sources.toml")
    sc.add_argument("--execute", action="store_true", help="actually download (default: dry-run)")
    sc.add_argument("--limit", type=int)
    sc.add_argument("--list", action="store_true", help="list configured sources")

    sub.add_parser("sources", help="list sources in the library")

    dm = sub.add_parser("demo", help="generate + import the CC0 demo dataset")
    dm.add_argument("--dir")
    dm.add_argument("--no-import", action="store_true")

    ex = sub.add_parser("export", help="export a portable dataset zip")
    ex.add_argument("out")

    idz = sub.add_parser("import-dataset", help="import a previously exported dataset zip")
    idz.add_argument("zip")

    bk = sub.add_parser("backup", help="full backup of the data directory")
    bk.add_argument("out")

    rs = sub.add_parser("restore", help="restore a full backup")
    rs.add_argument("zip")

    rm = sub.add_parser("remove", help="remove an asset or a whole source (and its files)")
    rm.add_argument("--asset", type=int)
    rm.add_argument("--source", type=int)

    sub.add_parser("stats", help="library statistics")

    sv = sub.add_parser("serve", help="start the local web app")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8080)

    return p


_DISPATCH = {
    "init": cmd_init, "import": cmd_import, "analyze": cmd_analyze, "critique": cmd_critique,
    "search": cmd_search, "tag": cmd_tag, "scrape": cmd_scrape, "sources": cmd_sources,
    "demo": cmd_demo, "export": cmd_export, "import-dataset": cmd_import_dataset,
    "backup": cmd_backup, "restore": cmd_restore, "remove": cmd_remove, "stats": cmd_stats,
    "serve": cmd_serve,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    configure_logging(settings.log_path)
    return _DISPATCH[args.command](args, settings)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
