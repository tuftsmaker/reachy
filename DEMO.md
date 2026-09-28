# Live demo script — "programming a robot with opencode"

A presenter's run sheet. Target: **12–15 minutes** with opencode on screen and
Reachy on the desk.

## 10 minutes before

```bash
# in a terminal window (keep it open), from the repo root:
zsh scripts/daemon.sh

# verify everything in one shot (speaker beeps at the end):
~/.venvs/reachy-mini/bin/python scripts/check.py --beep
```

- Robot powered from the wall supply, USB to the Mac, sitting clear of clutter.
- Keep the Mac awake (`caffeinate -dimsu &`) and its USB cable connected --
  the Lite has no onboard computer, so daemon + demos + cloud calls all run
  on the Mac.
- **Light matters**: the Lite camera is dim in low light and face detection
  needs a lit, frontal face. Put a desk lamp near the robot, aimed at where
  you (or volunteers) will sit.
- Have `demo/class_qa.py` open in a second terminal — or run it from
  opencode.

## The narrative

> "This robot shipped as an empty repo. In one opencode session we installed
> the SDK, found a loose motor cable inside the foot, worked around a port
> collision with my Tailscale setup, and got it to see, hear, speak, and
> move. Then we wrote these demos."

Keep the README open: the two "gotchas" are the best story.

## Act 1 — Hello (1 min)

```bash
~/.venvs/reachy-mini/bin/python demo/greet.py
```

Wakes up, waves its antennas, nods, chirps, strikes a pose.

## Act 2 — It sees me (2 min)

```bash
~/.venvs/reachy-mini/bin/python demo/face_tracking.py
```

Have someone sit in front of Reachy, well lit, **facing it** (profile views
and dark rooms defeat the detector). The head follows them. Ctrl+C to stop.

Talking point: detection runs in the daemon; the script is ~30 lines because
the SDK exposes `start_head_tracking()` / `get_tracked_face()`.

## Act 3 — It hears me (2 min)

```bash
~/.venvs/reachy-mini/bin/python demo/clap_antennas.py
```

Ask the audience to clap. The antennas spike with loudness and settle when
quiet. Try talking, whistling, music.

## Act 4 — Ask it about the class (4 min)

```bash
~/.venvs/reachy-mini/bin/python demo/class_qa.py
```

Press Enter, then ask out loud, e.g.:

- "Where does the second half of class happen?"
- "What do I need to bring to the laser cutting session?"
- "How is the course graded?"

The robot transcribes you (Deepgram), asks **DeepSeek V4.1 Flash** via Ollama
cloud with the syllabus as context, then answers out loud with head and
antenna gestures. Follow-ups work — it keeps the last few turns.

Show the one-line pipeline change live if there's time:

```bash
# fall back to a local model (no network needed):
~/.venvs/reachy-mini/bin/python demo/class_qa.py --model gpt-oss:20b
# type instead of speaking:
~/.venvs/reachy-mini/bin/python demo/class_qa.py --text
```

## Act 5 — It books office hours (3 min)

```bash
~/.venvs/reachy-mini/bin/python demo/book_office_hours.py \
    --name "Student Name" --email student@tufts.edu
```

Reachy reads the next open slots for the "Tufts Office Hours" event type.
Say which one works ("Tuesday at 10"), confirm, and it books **for real**
through the Calendly Scheduling API — calendar invite, Zoom link and
reminders are all handled by Calendly. Clean up test bookings with:

```bash
~/.venvs/reachy-mini/bin/python demo/schedule_demo.py --upcoming
~/.venvs/reachy-mini/bin/python demo/schedule_demo.py --cancel <event-uri>
```

Rehearse with `--dry-run` (never books) or drive it by typing with `--text`.

## Live-coding cards (give these to opencode on stage)

Each is a small, runnable change an agent can make in a minute or two:

1. **"Make Reachy nod yes when I say 'Reachy'."** (mic loop + wake-word check,
   `goto_target` nods)
2. **"Make it turn toward whoever is speaking."** (the SDK exposes a
   direction-of-arrival endpoint at `/api/state/doa` — see the SDK's
   `examples/sound_doa.py`)
3. **"Make the antennas do a Mexican wave."** (a timed loop over
   `set_target(antennas=...)`)
4. **"Add a 'thinking' face: head tilt plus slow antenna flick, until the
   answer is ready."** (`class_qa.py` already has `think_gesture()` — ask it
   to change the motion)
5. **"Have it introduce itself using my actual syllabus blurb."** (pull a
   paragraph from `demo/class_facts.md` into a new script)

## If something breaks

| Symptom | Fast fix |
|---|---|
| Nothing moves | Robot asleep/limp: `demo/greet.py` wakes it; check the daemon window is alive |
| Camera black | Move a lamp; re-run `scripts/check.py` |
| Face not detected | Sit closer, face the robot, brighten the room |
| Q&A can't hear you | `--text` mode (typed questions still speak answers) |
| Booking errors or no Zoom link | Rehearse `--dry-run`; fall back to `schedule_demo.py --link` (single-use booking URL) |
| No network | `--stt whisper` (local), `--model gpt-oss:20b` (local), `--tts say` (offline voice) |
| Daemon died | `zsh scripts/daemon.sh` again in its terminal |
| Everything is weird | `pkill -f reachy-daemon-localhost`, wait 5 s, restart daemon |

## After the demo

```bash
# stop the daemon: Ctrl+C in its terminal window
# robot off: press the On/Off switch, then unplug if you're done
```
