#!/bin/bash
# DCLM VPS bootstrap — run once on a fresh Ubuntu 22.04/24.04 box.
# Installs Docker, clones the build, starts the DCLM.
set -euo pipefail

REPO="digenova77-ui/efuse-unity"
BRANCH="main"
APP_DIR="/opt/dclm"

echo "=== DCLM VPS bootstrap ==="

# Docker
if ! command -v docker &>/dev/null; then
  echo "[+] Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  usermod -aG docker "$USER" || true
fi

# App directory
sudo mkdir -p "$APP_DIR"
sudo chown "$USER:$USER" "$APP_DIR"
cd "$APP_DIR"

# Clone (public repo — no auth needed for read)
if [ ! -d "efuse-unity" ]; then
  echo "[+] Cloning $REPO..."
  git clone --depth 1 --branch "$BRANCH" "https://github.com/$REPO.git"
fi
cd efuse-unity

# Build & start
echo "[+] Building DCLM container..."
docker compose -f vps/docker-compose.yml up -d --build

echo "[+] DCLM running. Check: docker compose -f vps/docker-compose.yml logs -f"
