#!/usr/bin/env bash
# One-shot reproducible dev setup for PixelForge AI (backend + frontend).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Backend: creating virtualenv and installing dependencies"
cd "$REPO_ROOT/backend"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip >/dev/null
.venv/bin/pip install -e ".[dev]"

if [[ "${PIXELFORGE_INSTALL_ML:-0}" == "1" ]]; then
  echo "==> Backend: installing ML extras (torch, diffusers) — this is large"
  .venv/bin/pip install -e ".[ml]"
fi

echo "==> Backend: running checks"
.venv/bin/ruff check src tests
.venv/bin/mypy src
.venv/bin/pytest -q

echo "==> Frontend: installing dependencies"
cd "$REPO_ROOT/frontend"
npm install

echo "==> Frontend: running checks"
npm run check

cat <<'EOF'

Setup complete.

  Run the backend:   cd backend && .venv/bin/uvicorn pixelforge.main:app --port 8765
  Run the app:       cd frontend && npm run dev
  Real inference:    PIXELFORGE_INSTALL_ML=1 ./scripts/setup.sh  (downloads FLUX weights on first generation)
EOF
