#!/bin/zsh
# Start the Reachy Mini daemon on macOS.
#
# Why this script exists (two macOS/Reachy gotchas):
#
#  1. macOS ties camera + microphone permission to the *app* hosting the
#     process. A daemon spawned from a background helper (like opencode)
#     cannot show the permission dialog, so it is silently denied. Running
#     the daemon from a terminal window -- which the system does let you
#     grant camera/mic access to -- fixes this. The request step below
#     triggers those permission dialogs on first run.
#
#  2. The stock daemon asks GStreamer's WebRTC element to run its signalling
#     server on 0.0.0.0:8443. If anything else owns port 8443 (e.g.
#     `tailscale serve`), the bind fails and the camera/audio feed stays
#     empty. scripts/reachy_daemon_localhost.py binds it to 127.0.0.1
#     instead, which coexists with anything on the tailnet addresses.
#
# Keep this window open while using the robot; Ctrl+C stops the daemon.
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/.venvs/reachy-mini/bin/python"
UV="$HOME/.local/bin/uv"

if [ ! -x "$PY" ]; then
  echo "No venv at $HOME/.venvs/reachy-mini -- run scripts/setup.sh first."
  exit 1
fi

if [ -x "$UV" ]; then
  echo "== Requesting camera/microphone access (click Allow on any dialogs) =="
  "$UV" run --no-project --with pyobjc-framework-AVFoundation --python 3.12 \
      python "$ROOT/scripts/request_access.py" || true
  echo
fi

echo "== Starting Reachy Mini daemon (keep this window open; Ctrl+C to stop) =="
exec "$PY" "$ROOT/scripts/reachy_daemon_localhost.py" --no-wake-up-on-start "$@"
