# Reachy Mini demo kit

Scripts and demos for a **Reachy Mini Lite** (RM-LK-01) driven from a Mac.
Everything in this repo was built in a single opencode session: the agent
diagnosed a loose motor cable in the robot's foot, worked around two
macOS-specific blockers, and wrote the demos below.

## What's here

| Path | What it does |
|------|--------------|
| `scripts/setup.sh` | One-time install: `uv` + a pinned Python 3.12 + the `reachy-mini` SDK into `~/.venvs/reachy-mini` |
| `scripts/daemon.sh` | Start the robot daemon. Run it in a **terminal window** and keep it open (see "Gotchas") |
| `scripts/check.py` | Quick health check: motors, camera, mic, speaker (`--beep` plays a tone) |
| `scripts/extract_class_facts.py` | Regenerate `demo/class_facts.md` from the ENT-164 syllabus |
| `scripts/reachy_daemon_localhost.py` | Daemon wrapper that binds the WebRTC signalling server to `127.0.0.1` (port 8443 fix) |
| `scripts/request_access.py` | Triggers the macOS camera/microphone permission dialogs |
| `demo/greet.py` | Scripted hello: wake-up, antenna wave, nod, three-note chirp |
| `demo/face_tracking.py` | Reachy follows the closest face (detection runs in the daemon) |
| `demo/clap_antennas.py` | Antennas jump with claps, music, or voices |
| `demo/class_qa.py` | Ask about the class; answers out loud, with body language |

## Quick start

```bash
# once
scripts/setup.sh

# every session: start the daemon in a terminal window, keep it open
zsh scripts/daemon.sh

# then run demos in another terminal
~/.venvs/reachy-mini/bin/python demo/greet.py
~/.venvs/reachy-mini/bin/python demo/face_tracking.py
```

## The two gotchas (and how this repo works around them)

**1. macOS camera/microphone permission belongs to the *app*, not the device.**
The Reachy Lite has no computer inside it: the robot's camera and microphone
are USB devices plugged into this Mac, and the daemon that reads them is a
child process of whatever app launched it. macOS only lets a *GUI app* show
the permission dialog, so a daemon launched from a background helper gets
silently denied. **Run `scripts/daemon.sh` from a terminal window** -- the
first run asks for camera and microphone access, you click Allow once, and
the daemon inherits it.

**2. Port 8443.** The stock daemon asks GStreamer's WebRTC element to run its
signalling server on `0.0.0.0:8443`. If anything else owns that port -- on
this machine, `tailscale serve` -- the bind fails, the media pipeline never
starts, and the camera/mic feed stays empty. `scripts/reachy_daemon_localhost.py`
binds the signalling server to `127.0.0.1` instead, which coexists with the
tailnet listener.

## The Mac *is* the robot's brain

Reachy Mini **Lite has no computer inside it**: the robot's motors, camera,
microphones and speaker are USB peripherals, and the daemon that drives them
runs on the host Mac. That means:

- The MacBook must stay connected (USB) while Reachy is in use. With only the
  power supply connected the robot is inert — motors limp, no behaviors.
- The Mac also needs internet for the default Q&A stack (Deepgram, Ollama
  cloud); every cloud piece has an offline fallback (see below).
- Keep the Mac awake while using it (`caffeinate -dimsu &`, or Energy
  settings) — sleep stops the daemon and the robot with it.

For true standalone operation you would need the Reachy Mini *Wireless*
(onboard Raspberry Pi + battery), or a small always-on Linux host wired to
the Lite instead of a laptop.

## Class Q&A (`demo/class_qa.py`)

The pipeline: **Reachy's mic → speech-to-text → LLM → speech synthesis →
Reachy's speaker**, with head/antenna body language.

- **Speech-to-text**: [Deepgram](https://deepgram.com) nova-3 if a key is
  configured, otherwise local whisper.cpp (`~/.cache/whisper.cpp/`). The key
  is optional and lives **outside the repo**:

  ```bash
  mkdir -p ~/.config/tuftsmaker
  printf '%s' 'YOUR_DEEPGRAM_KEY' > ~/.config/tuftsmaker/deepgram_key
  chmod 600 ~/.config/tuftsmaker/deepgram_key
  ```

  (`DEEPGRAM_API_KEY` in the environment also works.)

- **LLM**: any [Ollama](https://ollama.com) model. The default is
  `deepseek-v4.1-flash:cloud`; `--model` switches it, e.g. to a local model
  if the network is down.

- **Speech**: Deepgram Aura (`aura-asteria-en`) when a Deepgram key is
  configured, macOS `say` otherwise (instant, offline). Force either with
  `--tts say` / `--tts deepgram`.

- **Knowledge**: `demo/class_facts.md`, extracted from the ENT-164 syllabus
  (the course repo is the source of truth). Regenerate with:

  ```bash
  python scripts/extract_class_facts.py
  ```

Modes:

```bash
python demo/class_qa.py                 # voice: press Enter, then ask
python demo/class_qa.py --mode auto     # keep listening (voice activity)
python demo/class_qa.py --text          # type questions (no microphone)
```

## Troubleshooting

- Run `scripts/check.py` first: it reports daemon state, motor mode, camera
  frame, mic level, and (with `--beep`) the speaker.
- **Robot doesn't move**: it may be asleep/limp. The demos call
  `enable_motors()` themselves; if the head sits in the sleep pose the
  greeting wakes it.
- **Camera looks dark**: the Lite camera is weak in low light (known
  behavior); a desk lamp goes a long way.
- **No microphone samples**: the Q&A pipeline must call
  `start_recording()` before reading samples -- the demos do this for you.
- **Daemon busy / port 8000 in use**: another daemon is still running;
  `pkill -f reachy-daemon-localhost` (or Ctrl+C in its terminal).

## Credits

- [Reachy Mini SDK](https://github.com/pollen-robotics/reachy_mini) by Pollen
  Robotics & Hugging Face (Apache-2.0).
- Demos built with [opencode](https://opencode.ai).
