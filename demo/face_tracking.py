#!/usr/bin/env python3
"""Face tracking: Reachy follows the closest face (detection runs in the daemon).

Usage:
    ~/.venvs/reachy-mini/bin/python demo/face_tracking.py [--seconds 60]

Press Ctrl+C to stop early.
"""

import argparse
import time

from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=0, help="0 = run until Ctrl+C")
    args = ap.parse_args()

    with ReachyMini() as mini:
        mini.enable_motors()
        time.sleep(0.3)

        # Lift the head to an attentive pose before tracking takes over.
        mini.goto_target(
            head=create_head_pose(z=12, degrees=True, mm=True),
            antennas=[0.2, -0.2],
            duration=0.9,
        )

        mini.start_head_tracking()
        print("Head tracking ON -- Reachy is watching. Ctrl+C to stop.")
        start = time.time()
        try:
            while args.seconds <= 0 or time.time() - start < args.seconds:
                face = mini.get_tracked_face()
                if face.detected:
                    print(f"  face at x={face.x:+.2f} y={face.y:+.2f}")
                else:
                    print("  no face")
        except KeyboardInterrupt:
            pass
        finally:
            mini.stop_head_tracking()
            print("Head tracking OFF")


if __name__ == "__main__":
    main()
