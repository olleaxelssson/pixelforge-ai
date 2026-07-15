/** Centralized frontend configuration. */
export const BACKEND_HOST = "127.0.0.1";
export const BACKEND_PORT = 8765;
export const API_BASE_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;
export const WS_BASE_URL = `ws://${BACKEND_HOST}:${BACKEND_PORT}`;
export const AUTOSAVE_INTERVAL_MS = 60_000;
export const UNDO_HISTORY_LIMIT = 100;
