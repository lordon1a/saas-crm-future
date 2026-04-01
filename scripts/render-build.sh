#!/usr/bin/env bash
set -euo pipefail

echo "[render-build] Installing Python dependencies"
pip install -r requirements.txt

if [ -d "workflow-ui" ]; then
  echo "[render-build] Building workflow-ui bundle"
  cd workflow-ui
  npm ci --no-audit --no-fund
  npm run build
  cd ..
else
  echo "[render-build] workflow-ui directory not found, skipping frontend build"
fi

echo "[render-build] Build completed"
