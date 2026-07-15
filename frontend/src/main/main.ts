/**
 * Electron main process: window management and backend supervision.
 * In development the backend is expected to be started separately
 * (`uvicorn pixelforge.main:app`); in production it is spawned here.
 */
import { spawn, ChildProcess } from "node:child_process";
import path from "node:path";

import { app, BrowserWindow } from "electron";

import { API_BASE_URL } from "../shared/config";

let backendProcess: ChildProcess | null = null;

async function backendIsRunning(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`);
    return response.ok;
  } catch {
    return false;
  }
}

async function ensureBackend(): Promise<void> {
  if (await backendIsRunning()) return;
  const python = process.env.PIXELFORGE_PYTHON ?? "python3";
  backendProcess = spawn(python, ["-m", "pixelforge.main"], {
    stdio: "inherit",
    env: { ...process.env },
  });
  for (let attempt = 0; attempt < 60; attempt++) {
    if (await backendIsRunning()) return;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  console.error("PixelForge backend did not become healthy in time");
}

function createWindow(): void {
  const window = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    backgroundColor: "#101014",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  const devServerUrl = process.env.VITE_DEV_SERVER_URL;
  if (devServerUrl) {
    void window.loadURL(devServerUrl);
  } else {
    void window.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

app.whenReady().then(async () => {
  await ensureBackend();
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("quit", () => {
  backendProcess?.kill();
});
