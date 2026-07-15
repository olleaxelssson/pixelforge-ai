/** Preload script: expose a minimal, safe bridge to the renderer. */
import { contextBridge } from "electron";

contextBridge.exposeInMainWorld("pixelforge", {
  platform: process.platform,
  versions: { electron: process.versions.electron },
});
