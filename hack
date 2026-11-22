#!/bin/sh
# Project command line for macOS/Linux: ./hack help   (Windows: hack.cmd)
# Makes sure uv exists, then runs scripts/hack.py with a uv-managed Python.
set -e
root=$(cd "$(dirname "$0")" && pwd)

uv=$(command -v uv 2>/dev/null || true)
[ -z "$uv" ] && [ -x "$HOME/.local/bin/uv" ] && uv="$HOME/.local/bin/uv"
if [ -z "$uv" ]; then
  echo "uv (Python + package manager) is missing, installing it..."
  if command -v brew >/dev/null 2>&1; then
    brew install uv
    uv=$(command -v uv)
  else
    curl -LsSf https://astral.sh/uv/install.sh | sh
    uv="$HOME/.local/bin/uv"
  fi
fi

exec "$uv" run --quiet --script "$root/scripts/hack.py" "$@"
