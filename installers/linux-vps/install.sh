#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -eq 0 ]]; then echo 'Run as a regular sudo-capable user, not root.'; exit 1; fi
command -v docker >/dev/null || { echo 'Install Docker Engine and Compose plugin first.'; exit 1; }
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
echo 'Preflight: memory, storage, architecture'
free -h
df -h "$APP_DIR"
uname -m
cd "$APP_DIR"
if [[ ! -f .env ]]; then cp .env.example .env; chmod 600 .env; echo 'Created .env. Set strong secrets, then rerun this script.'; exit 0; fi
docker compose config >/dev/null
docker compose up -d --build
MODEL="$(grep -E '^MODEL_NAME=' .env | cut -d= -f2-)"
docker compose exec -T ollama ollama pull "${MODEL:-qwen2.5:3b}"
docker compose ps
