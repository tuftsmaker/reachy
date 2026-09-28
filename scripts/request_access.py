#!/usr/bin/env python3
"""Trigger macOS camera/microphone permission prompts.

Run from inside the OpenCode process tree so TCC records the responsible app.
Waiting on the completion handler lets the system dialog be answered before
the process exits.
"""

import sys
import threading

from AVFoundation import AVCaptureDevice


def request(media_type: str, label: str):
    done = threading.Event()
    result: dict = {}

    def handler(granted):
        result["granted"] = bool(granted)
        done.set()

    print(f"requesting {label} access...", flush=True)
    AVCaptureDevice.requestAccessForMediaType_completionHandler_(media_type, handler)
    if not done.wait(timeout=180):
        print(f"{label}: no answer within 180s", flush=True)
        return None
    print(f"{label}: granted={result.get('granted')}", flush=True)
    return result.get("granted")


def main():
    video = request("vide", "camera")
    audio = request("soun", "microphone")
    print(f"FINAL camera={video} microphone={audio}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
