#!/usr/bin/env python3
"""Book office hours through Reachy, by voice.

Flow: Reachy reads the next open office-hours slots, you say which one works,
it confirms, then books it through the Calendly Scheduling API (Zoom link and
calendar invite handled by Calendly).

Usage:
    python demo/book_office_hours.py --name "Your Name" --email you@tufts.edu
    python demo/book_office_hours.py --dry-run          # never actually books
    python demo/book_office_hours.py --text             # type instead of speak
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))

import calendly_tools as cal  # noqa: E402
import class_qa as qa  # noqa: E402
from reachy_mini import ReachyMini  # noqa: E402
from reachy_mini.utils import create_head_pose  # noqa: E402

YES_WORDS = {"yes", "yeah", "yep", "yup", "sure", "please", "ok", "okay",
             "go ahead", "book it", "do it", "confirm", "sounds good"}

DECISION_PROMPT = """You are Reachy Mini, a robot scheduling office hours with a \
student. The student said: "{request}".

Open office-hours slots (ISO time | human readable):
{slots}

Pick the slot that best matches what the student asked for. Reply with JSON only:
{{"slot": "<the ISO time from the list, or null if nothing matches>",
  "speech": "<one short spoken sentence proposing that time, or asking them to pick again>"}}"""


def speak_slot(iso: str, tz: str) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo(tz))
    return dt.strftime("%A %B %-d at %-I:%M %p %Z")


def speak_text(mini: ReachyMini, text: str, tts: str, voice: str, dg_voice: str, key: str) -> None:
    suffix = ".wav" if tts == "say" else ".mp3"
    path = str(Path(tempfile.gettempdir()) / f"reachy-sched{suffix}")
    if tts == "say":
        qa.synth_say(text, voice, path)
    else:
        qa.synth_deepgram(text, dg_voice, key, path)
    mini.media.play_sound(path)
    qa.animate_speaking(mini, qa.audio_duration(path) + 0.2)


def parse_decision(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {"slot": None, "speech": raw.strip()}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"slot": None, "speech": raw.strip()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--event", default="Tufts Office Hours", help="Calendly event type name substring")
    ap.add_argument("--name", default="Demo Student")
    ap.add_argument("--email", default="")
    ap.add_argument("--tz", default="America/New_York")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--max-slots", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true", help="never actually book")
    ap.add_argument("--text", action="store_true", help="type instead of speaking")
    ap.add_argument("--model", default="deepseek-v4.1-flash:cloud")
    ap.add_argument("--stt", choices=["auto", "deepgram", "whisper"], default="auto")
    ap.add_argument("--tts", choices=["auto", "say", "deepgram"], default="auto")
    ap.add_argument("--voice", default="Samantha")
    ap.add_argument("--deepgram-model", default="nova-3")
    ap.add_argument("--deepgram-voice", default="aura-asteria-en")
    args = ap.parse_args()

    if not args.email:
        sys.exit("--email is required for booking (the calendar invite goes there)")

    key = qa.deepgram_key()
    stt = args.stt if args.stt != "auto" else ("deepgram" if key else "whisper")
    tts = args.tts if args.tts != "auto" else ("deepgram" if key else "say")

    event = cal.find_event_type(args.event)
    slots = cal.available_times(event["uri"], days=args.days)[: args.max_slots]
    if not slots:
        print("no available slots")
        return
    printable = [f"{s['start_time']} | {speak_slot(s['start_time'], args.tz)}" for s in slots]
    print("slots:")
    for line in printable:
        print("  " + line)

    def ask(question: str) -> str:
        if args.text:
            return input(f"❯ ({question}) ").strip()
        audio = qa.record_question(mini, ambient, enter=True)
        if audio is None:
            return ""
        try:
            if stt == "deepgram":
                return qa.transcribe_deepgram(audio, key, args.deepgram_model)
            return qa.transcribe_whisper(audio, qa.WHISPER_MODEL)
        except Exception as e:
            print("[stt] error:", e)
            return ""

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
                    calibration.append(qa.rms(s))
                time.sleep(0.02)
            if calibration:
                ambient = max(0.002, sum(calibration) / len(calibration))
            print(f"[mic] ambient rms={ambient:.4f}")

        offer = ", ".join(speak_slot(s["start_time"], args.tz) for s in slots[:3])
        speak_text(mini, f"I have office hours open: {offer}. Which one works for you?",
                   tts, args.voice, args.deepgram_voice, key)

        request = ask("which time?")
        print(f"❯ {request}")
        if not request:
            speak_text(mini, "I didn't catch that. Try again any time.", tts, args.voice, args.deepgram_voice, key)
            return

        qa.think_gesture(mini)
        raw = qa.ask_llm(
            args.model,
            [{"role": "user", "content": DECISION_PROMPT.format(request=request, slots="\n".join(printable))}],
        )
        decision = parse_decision(raw)
        slot, speech = decision.get("slot"), decision.get("speech") or ""

        if not slot:
            speak_text(mini, speech or "I couldn't match that to a slot. Let's try again.", tts, args.voice, args.deepgram_voice, key)
            return

        confirm = ask("confirm?")
        print(f"❯ {confirm}")
        if not any(word in confirm.lower() for word in YES_WORDS):
            speak_text(mini, "No problem, nothing booked. Let me know when you want a slot.", tts, args.voice, args.deepgram_voice, key)
            return

        if args.dry_run:
            speak_text(mini, f"Dry run: I would have booked {speak_slot(slot, args.tz)} for {args.name}.", tts, args.voice, args.deepgram_voice, key)
            print(f"[dry-run] would book {slot} for {args.name} <{args.email}>")
            return

        qa.think_gesture(mini)
        try:
            kind = cal.location_kind(event["uri"])
            invitee = cal.book(event["uri"], slot, args.name, args.email, args.tz, kind)
            print(f"[booked] {invitee['event']}")
            speak_text(
                mini,
                f"Done! I booked {speak_slot(slot, args.tz)}. Check your email for the calendar invite and Zoom link.",
                tts, args.voice, args.deepgram_voice, key,
            )
            mini.goto_target(
                head=create_head_pose(z=14, roll=10, yaw=-6, degrees=True, mm=True),
                antennas=[0.5, 0.5], duration=0.8,
            )
        except Exception as e:
            print("[book] error:", e)
            speak_text(mini, "I couldn't complete the booking. The calendar returned an error.", tts, args.voice, args.deepgram_voice, key)
        finally:
            if not args.text:
                mini.media.stop_recording()
            mini.goto_target(head=create_head_pose(), antennas=[0.15, -0.15], duration=0.6)


if __name__ == "__main__":
    main()
