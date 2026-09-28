#!/usr/bin/env python3
"""Launch the Reachy Mini daemon with its WebRTC signalling server bound to
localhost only.

Why: the stock daemon sets `run-signalling-server=True` on gst webrtcsink,
whose signalling server binds 0.0.0.0:8443. On this Mac, port 8443 is already
held by `tailscale serve` on the tailnet addresses, so the bind fails and the
whole media pipeline never reaches PLAYING -- the camera/audio IPC feed stays
empty and SDK `get_frame()` / `get_audio_sample()` return None.

Binding to 127.0.0.1 avoids the clash (same port, different address) and is
all local SDK/desktop-app clients need on a USB-tethered Lite.

Usage:  ~/.venvs/reachy-mini/bin/python reachy-daemon-localhost.py [daemon args]
"""

import sys

from reachy_mini.media import media_server as _ms

_orig_configure_webrtc = _ms.GstMediaServer._configure_webrtc


def _configure_webrtc_localhost(self, pipeline):
    el = _orig_configure_webrtc(self, pipeline)
    el.set_property("signalling-server-host", "127.0.0.1")
    return el


_ms.GstMediaServer._configure_webrtc = _configure_webrtc_localhost

from reachy_mini.daemon.app.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
