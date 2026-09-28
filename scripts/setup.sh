#!/bin/zsh
# One-time setup for the Reachy Mini SDK on macOS.
#
# Installs uv (user-space, no shell profile changes), a pinned CPython 3.12,
# and the SDK into ~/.venvs/reachy-mini.
set -eu

VENV="$HOME/.venvs/reachy-mini"
UV="$HOME/.local/bin/uv"

if [ ! -x "$UV" ]; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh
fi

echo "Installing Python 3.12 (managed by uv)..."
"$UV" python install 3.12

echo "Creating venv at $VENV..."
"$UV" venv --python 3.12 --python-preference only-managed "$VENV"

echo "Installing reachy-mini + pillow..."
"$UV" pip install --python "$VENV/bin/python" "reachy-mini" pillow

echo
echo "Done. Next: run scripts/daemon.sh in a terminal window."
