#!/usr/bin/env python3
"""Sound-reactive antennas: they jump with claps, music, or voices.

Usage:
    ~/.venvs/reachy-mini/bin/python demo/clap_antennas.py [--seconds 60]
"""

import argparse
import time

import numpy as np

from reachy_mini import ReachyMini


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--gain", type=float, default=10.0, help="mic level multiplier")
    ap.add_argument("--max-angle", type=float, default=1.0, help="antenna travel, radians")
    args = ap.parse_args()

    with ReachyMini() as mini:
        mini.enable_motors()
        time.sleep(0.3)
        mini.media.start_recording()
        time.sleep(0.8)

        level = 0.0
        start = time.time()
        last_print = 0.0
        print("Listening... clap, talk, or play music. Ctrl+C to stop.")
        try:
            while time.time() - start < args.seconds:
                sample = mini.media.get_audio_sample()
                if sample is not None:
                    values = np.asarray(sample, dtype=np.float64)
                    loudness = float(np.sqrt(np.mean(values**2)))
                    # instant attack, smooth decay
                    level = max(level * 0.90, min(1.0, loudness * args.gain))
                    mini.set_target(
                        antennas=[level * args.max_angle, -level * args.max_angle]
                    )
                    now = time.time()
                    if now - last_print > 0.25:
                        last_print = now
                        print(f"  {level:4.2f} {'#' * int(level * 40)}", flush=True)
                time.sleep(0.02)
        except KeyboardInterrupt:
            pass
        finally:
            mini.media.stop_recording()
            mini.goto_target(antennas=[0.0, 0.0], duration=0.4)
            print("done")


if __name__ == "__main__":
    main()
