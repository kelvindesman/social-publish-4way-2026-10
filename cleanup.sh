#!/usr/bin/env bash
# Remove everything this POC created. Touches only poc-* resources, never other projects.
set -euo pipefail
cd "$(dirname "$0")"
echo "before:"; docker system df
POC_ENV_FILE=/dev/null docker compose down -v --rmi all --remove-orphans || true
docker images --filter label=poc=1 -q | sort -u | xargs -r docker rmi -f
docker volume ls --filter label=poc=1 -q | xargs -r docker volume rm
docker builder prune -f --filter label=poc=1
echo "after:"; docker system df
echo "left over poc images: $(docker images --filter label=poc=1 -q | wc -l | tr -d ' ')"
