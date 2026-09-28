#!/usr/bin/env python3
"""Scripted greeting: wake up, wave the antennas, nod, chirp, strike a pose.

Usage:
    ~/.venvs/reachy-mini/bin/python demo/greet.py
"""

import math
import struct
import tempfile
import time
import wave

from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

SAMPLE_RATE = 16000


def chirp(path: str) -> None:
    """Write a small rising three-note melody (C5-E5-G5) as a WAV file."""
    notes = [(523.25, 0.18), (659.25, 0.18), (783.99, 0.30)]
    frames = bytearray()
    for freq, dur in notes:
        n = int(SAMPLE_RATE * dur)
        for i in range(n):
            attack = min(1.0, i / (0.02 * SAMPLE_RATE))
            release = min(1.0, (n - i) / (0.05 * SAMPLE_RATE))
            value = int(9000 * attack * release * math.sin(2 * math.pi * freq * i / SAMPLE_RATE))
            frames += struct.pack("<h", value)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(frames))


def main() -> None:
    with ReachyMini() as mini:
        print("[greet] enabling motors")
        mini.enable_motors()
        time.sleep(0.3)

        print("[greet] waking up")
        mini.wake_up()
        time.sleep(1.5)

        print("[greet] antenna wave")
        for side in (+1, -1):
            mini.goto_target(antennas=[0.9 * side, -0.9 * side], duration=0.35)
            time.sleep(0.05)
        mini.goto_target(antennas=[0.0, 0.0], duration=0.35)

        print("[greet] nod")
        for _ in range(2):
            mini.goto_target(head=create_head_pose(pitch=14, degrees=True), duration=0.30)
            mini.goto_target(head=create_head_pose(pitch=-4, degrees=True), duration=0.30)

        print("[greet] happy pose + chirp")
        mini.goto_target(
            head=create_head_pose(z=12, roll=-12, yaw=8, degrees=True, mm=True),
            antennas=[0.5, 0.5],
            duration=0.8,
        )
        wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        chirp(wav)
        mini.media.play_sound(wav)
        time.sleep(1.3)

        print("[greet] settle")
        mini.goto_target(
            head=create_head_pose(), antennas=[0.2, -0.2], duration=0.8
        )
        print("[greet] hello!")


if __name__ == "__main__":
    main()
