#!/usr/bin/env python3
"""Ask Reachy about the class, and it answers out loud.

Pipeline:
    Reachy mic  ->  speech-to-text   (Deepgram nova-3, or local whisper.cpp)
                ->  LLM              (Ollama; default deepseek-v4.1-flash:cloud)
                ->  speech synthesis (macOS `say`, or Deepgram Aura)
                ->  Reachy speaker + head/antenna body language

Usage:
    python demo/class_qa.py                # voice, press Enter to ask
    python demo/class_qa.py --mode auto    # keep listening (voice activity)
    python demo/class_qa.py --text         # type questions (no STT)

The class context comes from demo/class_facts.md, regenerated from the ENT-164
syllabus with scripts/extract_class_facts.py.

Deepgram key (optional, enables the better STT):
    mkdir -p ~/.config/tuftsmaker
    printf '%s' 'YOUR_KEY' > ~/.config/tuftsmaker/deepgram_key
    chmod 600 ~/.config/tuftsmaker/deepgram_key
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import subprocess
import tempfile
import time
import urllib.request
import wave
from pathlib import Path

import numpy as np

from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

SAMPLE_RATE = 16000
WHISPER_MODEL = Path.home() / ".cache/whisper.cpp/ggml-base.en.bin"
DEEPGRAM_KEY_FILE = Path.home() / ".config/tuftsmaker/deepgram_key"

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
DEEPGRAM_STT_URL = "https://api.deepgram.com/v1/listen"
DEEPGRAM_TTS_URL = "https://api.deepgram.com/v1/speak"

SYSTEM_PROMPT = """You are Reachy Mini, a friendly desktop robot assistant answering spoken \
questions about the course ENT-164 "Intro to Making" at Tufts University.

Rules:
- Keep every answer short: 1-3 sentences, conversational. It is read aloud.
- Never use markdown, bullet points, or emoji.
- Use the CLASS CONTEXT below for class facts (dates, policies, assignments).
  If something is not covered there, say you are not sure and suggest checking
  the syllabus.
- If the question is not about the class, answer briefly and helpfully anyway.

CLASS CONTEXT:
{context}
"""


# ---------------------------------------------------------------- helpers


def deepgram_key() -> str:
    key = os.environ.get("DEEPGRAM_API_KEY", "").strip()
    if key:
        return key
    if DEEPGRAM_KEY_FILE.exists():
        return DEEPGRAM_KEY_FILE.read_text(encoding="utf-8").strip()
    return ""


def load_facts(path: Path) -> str:
    if not path.exists():
        raise SystemExit(
            f"Class facts not found at {path}\n"
            "Run: python scripts/extract_class_facts.py"
        )
    return path.read_text(encoding="utf-8")


def rms(chunk: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.asarray(chunk, dtype=np.float64) ** 2)))


def audio_to_wav_bytes(audio: np.ndarray) -> bytes:
    buf = io.BytesIO()
    pcm16 = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm16.tobytes())
    return buf.getvalue()


def audio_duration(path: str) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=10,
        )
        return max(0.5, float(out.stdout.strip()))
    except Exception:
        return 3.0


# ---------------------------------------------------------------- STT


def transcribe_deepgram(audio: np.ndarray, key: str, model: str) -> str:
    req = urllib.request.Request(
        f"{DEEPGRAM_STT_URL}?model={model}&smart_format=true&punctuate=true&language=en",
        data=audio_to_wav_bytes(audio),
        headers={"Authorization": f"Token {key}", "Content-Type": "audio/wav"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    return data["results"]["channels"][0]["alternatives"][0].get("transcript", "").strip()


def transcribe_whisper(audio: np.ndarray, model_path: Path) -> str:
    if not model_path.exists():
        raise RuntimeError(f"whisper model not found: {model_path}")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_to_wav_bytes(audio))
        wav_path = f.name
    try:
        out = subprocess.run(
            ["whisper-cli", "-m", str(model_path), "-f", wav_path, "-l", "en", "-nt", "-np"],
            capture_output=True, text=True, timeout=180,
        )
        return " ".join(line.strip() for line in out.stdout.splitlines() if line.strip())
    finally:
        os.unlink(wav_path)


# ---------------------------------------------------------------- LLM + TTS


def ask_llm(model: str, messages: list, timeout: float = 180.0) -> str:
    payload = json.dumps({"model": model, "messages": messages, "stream": False}).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    return (data.get("message") or {}).get("content", "").strip()


def synth_say(text: str, voice: str, path: str) -> None:
    subprocess.run(
        [
            "say", "-v", voice,
            "--file-format=WAVE", "--data-format=LEI16@22050",
            "-o", path, text,
        ],
        check=True,
    )


def synth_deepgram(text: str, voice: str, key: str, path: str) -> None:
    req = urllib.request.Request(
        f"{DEEPGRAM_TTS_URL}?model={voice}",
        data=json.dumps({"text": text}).encode(),
        headers={"Authorization": f"Token {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        Path(path).write_bytes(resp.read())


# ---------------------------------------------------------------- recording


def drain(mini: ReachyMini, seconds: float = 0.3) -> None:
    t0 = time.time()
    while time.time() - t0 < seconds:
        mini.media.get_audio_sample()
        time.sleep(0.02)


def record_question(
    mini: ReachyMini,
    ambient: float,
    enter: bool,
    wait_for_speech: float = 5.0,
    max_seconds: float = 20.0,
    silence: float = 0.9,
) -> np.ndarray | None:
    """Record one question. In `enter` mode, wait for Enter first; otherwise
    wait for speech onset. Returns mono float32 audio, or None."""
    onset = max(0.008, ambient * 3.5)
    quiet = onset * 0.5

    if enter:
        input("  press Enter, then ask your question ")
        drain(mini, 0.3)

    chunks: list[np.ndarray] = []
    recording = False
    speech_start = 0.0
    last_voice = 0.0
    t_start = time.time()

    while time.time() - t_start < max_seconds:
        sample = mini.media.get_audio_sample()
        if sample is None:
            time.sleep(0.01)
            continue
        mono = np.asarray(sample, dtype=np.float32).mean(axis=1)
        chunks.append(mono)
        level = rms(mono)
        now = time.time()

        if not recording:
            if level > onset:
                recording = True
                speech_start = now
                last_voice = now
            elif not enter and now - t_start > wait_for_speech:
                return None
        else:
            if level > quiet:
                last_voice = now
            if last_voice and now - last_voice > silence and now - speech_start > 0.4:
                break

    if not recording:
        return None
    return np.concatenate(chunks)


# ---------------------------------------------------------------- gestures


def think_gesture(mini: ReachyMini) -> None:
    mini.goto_target(
        head=create_head_pose(pitch=-6, roll=8, degrees=True),
        antennas=[0.5, 0.5],
        duration=0.5,
    )


def animate_speaking(mini: ReachyMini, seconds: float) -> None:
    t0 = time.time()
    while time.time() - t0 < seconds:
        t = time.time() - t0
        ant = 0.35 * math.sin(2 * math.pi * 0.7 * t)
        bob = 3.0 * math.sin(2 * math.pi * 0.45 * t)
        roll = 2.5 * math.sin(2 * math.pi * 0.35 * t + 1.0)
        mini.set_target(
            head=create_head_pose(z=bob, roll=roll, degrees=True, mm=True),
            antennas=[ant, -ant],
        )
        time.sleep(0.05)
    mini.goto_target(
        head=create_head_pose(), antennas=[0.15, -0.15], duration=0.6
    )


# ---------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="deepseek-v4.1-flash:cloud", help="Ollama model")
    ap.add_argument("--facts", default=str(Path(__file__).parent / "class_facts.md"))
    ap.add_argument("--mode", choices=["enter", "auto"], default="enter")
    ap.add_argument("--text", action="store_true", help="type questions instead of speaking")
    ap.add_argument("--stt", choices=["auto", "deepgram", "whisper"], default="auto")
    ap.add_argument("--tts", choices=["say", "deepgram"], default="say")
    ap.add_argument("--voice", default="Samantha", help="macOS `say` voice")
    ap.add_argument("--deepgram-model", default="nova-3")
    ap.add_argument("--deepgram-voice", default="aura-asteria-en")
    ap.add_argument("--seconds", type=float, default=0, help="0 = run until Ctrl+C")
    args = ap.parse_args()

    key = deepgram_key()
    stt = args.stt
    if stt == "auto":
        stt = "deepgram" if key else "whisper"
    if stt == "deepgram" and not key:
        raise SystemExit(
            "Deepgram selected but no key found. Put it in "
            "~/.config/tuftsmaker/deepgram_key or set DEEPGRAM_API_KEY."
        )
    if args.tts == "deepgram" and not key:
        raise SystemExit("Deepgram TTS needs a key (see --stt deepgram note).")

    facts = load_facts(Path(os.path.expanduser(args.facts)))
    system = SYSTEM_PROMPT.format(context=facts)

    with ReachyMini() as mini:
        mini.enable_motors()
        mini.goto_target(
            head=create_head_pose(z=12, degrees=True, mm=True),
            antennas=[0.2, -0.2], duration=0.9,
        )

        ambient = 0.004
        if not args.text:
            mini.media.start_recording()
            time.sleep(0.8)
            calibration = []
            t0 = time.time()
            while time.time() - t0 < 1.0:
                s = mini.media.get_audio_sample()
                if s is not None:
                    calibration.append(np.asarray(s, dtype=np.float32).mean(axis=1))
                time.sleep(0.02)
            if calibration:
                ambient = max(0.002, rms(np.concatenate(calibration)))
            print(f"[mic] calibrated, ambient rms={ambient:.4f}")

        print(f"Reachy class Q&A | model={args.model} | stt={stt} | tts={args.tts}")
        print("Ask a question about ENT-164. Ctrl+C to stop.\n")

        history: list = []
        t_start = time.time()
        try:
            while args.seconds <= 0 or time.time() - t_start < args.seconds:
                if args.text:
                    try:
                        question = input("❯ ").strip()
                    except EOFError:
                        break
                    if not question:
                        continue
                else:
                    audio = record_question(mini, ambient, enter=(args.mode == "enter"))
                    if audio is None or len(audio) < SAMPLE_RATE * 0.2:
                        print("(didn't catch that)")
                        continue
                    print("[stt] transcribing...")
                    try:
                        if stt == "deepgram":
                            question = transcribe_deepgram(audio, key, args.deepgram_model)
                        else:
                            question = transcribe_whisper(audio, WHISPER_MODEL)
                    except Exception as e:
                        print(f"[stt] error: {e}")
                        continue
                    if not question:
                        print("(didn't catch that)")
                        continue
                    print(f"❯ {question}")

                think_gesture(mini)
                messages = (
                    [{"role": "system", "content": system}]
                    + history
                    + [{"role": "user", "content": question}]
                )
                try:
                    answer = ask_llm(args.model, messages)
                except Exception as e:
                    print(f"[llm] error: {e}")
                    continue
                if not answer:
                    print("[llm] empty answer")
                    continue
                print(f"Reachy: {answer}\n")
                history = (
                    history
                    + [
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": answer},
                    ]
                )[-6:]

                suffix = ".wav" if args.tts == "say" else ".mp3"
                path = str(Path(tempfile.gettempdir()) / f"reachy-answer{suffix}")
                try:
                    if args.tts == "say":
                        synth_say(answer, args.voice, path)
                    else:
                        synth_deepgram(answer, args.deepgram_voice, key, path)
                    mini.media.play_sound(path)
                    animate_speaking(mini, audio_duration(path) + 0.2)
                except Exception as e:
                    print(f"[tts] error: {e}")
        except KeyboardInterrupt:
            pass
        finally:
            if not args.text:
                mini.media.stop_recording()
            mini.goto_target(head=create_head_pose(), antennas=[0.1, -0.1], duration=0.5)
            print("\nbye")


if __name__ == "__main__":
    main()
