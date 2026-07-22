# PixelForge AI — Standalone build

A **client-only** PixelForge that runs with no Python backend and no install: a seeded
procedural pixel-art **generator**, a pixel **editor** (pencil / eraser / fill / eyedropper +
undo), and a **palette lab** — all in one self-contained file.

## 1. Just the HTML (no build needed)

Open **`pixelforge.html`** in any modern browser — double-click it, or drag it onto a browser
window. That's the whole app; everything (styles, palettes, generator, editor) is inlined, so it
works offline from a `file://` URL. Generated sprites and edits export as PNG.

## 2. Desktop executable (.exe / AppImage)

The `electron/` folder wraps the same `pixelforge.html` in a minimal Electron shell and builds
native executables with **electron-builder**. Two commands:

```bash
cd standalone/electron
npm install          # downloads the Electron runtime
npm run dist         # → dist/ : Windows .exe (zip), Linux AppImage + tar.gz
```

Output (in `standalone/electron/dist/`):

- **Windows** — `PixelForge-1.0.0-win.zip` — unzip and run `PixelForge.exe` (no installer, no
  admin rights). Built with the `win: zip` target so **no code-signing / wine is required**.
- **Linux** — `PixelForge-1.0.0.AppImage` (chmod +x and run) and a `.tar.gz` (extract → run the
  `pixelforge` binary), plus an unpacked `linux-unpacked/` folder.

To target one platform only: `npx electron-builder --win` or `npx electron-builder --linux`.
For a Windows **installer** (`.exe` NSIS setup) instead of the portable zip, add `"nsis"` to the
`build.win.target` array in `electron/package.json` — that path needs `wine` on a Linux build host.

> Note: this build could not be produced inside the Claude Code sandbox because the Electron
> runtime download host (`github.com/electron/electron/releases`) is blocked by the environment's
> egress policy. Run the two commands above on any machine with normal internet access.

## Files

| File | What it is |
| --- | --- |
| `pixelforge.html` | The entire standalone app (open directly in a browser). |
| `electron/main.js` | Electron main process — opens a window that loads `pixelforge.html`. |
| `electron/package.json` | Electron + electron-builder deps and the Windows/Linux build targets. |
| `electron/pixelforge.html` | A copy bundled into the desktop build (kept in sync with the root one). |
