#!/usr/bin/env python3
"""Reachy Mini health check: daemon, motors, camera, microphone, speaker.

Usage:
    ~/.venvs/reachy-mini/bin/python scripts/check.py [--beep]
"""

import argparse
import math
import struct
import time
import wave

import numpy as np

from reachy_mini import ReachyMini


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--beep", action="store_true", help="also play a test tone on the speaker")
    args = ap.parse_args()

    with ReachyMini() as mini:
        status = mini.client.get_status()
        backend = status.backend_status
        ready = getattr(backend, "ready", None)
        mode = getattr(backend, "motor_control_mode", None)
        stats = getattr(backend, "control_loop_stats", None)
        freq = getattr(stats, "mean_control_loop_frequency", None)
        loop_txt = f" loop={freq:.1f}Hz" if freq else ""
        print(f"[daemon] state={status.state} ready={ready} motor_mode={mode}{loop_txt}")

        frame = mini.media.get_frame()
        if frame is None:
            print("[camera] NO FRAME")
        else:
            print(f"[camera] frame {frame.shape}")

        mini.media.start_recording()
        time.sleep(0.8)
        samples = []
        t0 = time.time()
        while time.time() - t0 < 1.0:
            s = mini.media.get_audio_sample()
            if s is not None:
                samples.append(np.asarray(s, dtype=np.float64).ravel())
            time.sleep(0.02)
        mini.media.stop_recording()

        if samples:
            audio = np.concatenate(samples)
            rms = float(np.sqrt(np.mean(audio**2)))
            print(f"[mic] {audio.shape[0]} samples rms={rms:.5f}")
        else:
            print("[mic] NO SAMPLES")

        if args.beep:
            path = "/tmp/reachy-check-beep.wav"
            sr = 16000
            frames = b"".join(
                struct.pack("<h", int(9000 * math.sin(2 * math.pi * 660 * i / sr)))
                for i in range(int(sr * 0.5))
            )
            with wave.open(path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes(frames)
            mini.media.play_sound(path)
            time.sleep(1.0)
            print("[speaker] beep played")


if __name__ == "__main__":
    main()
