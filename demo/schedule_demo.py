#!/usr/bin/env python3
"""Calendly helper CLI for the robot demos.

Usage:
    python demo/schedule_demo.py --list
    python demo/schedule_demo.py --slots --event "office hours" [--days 7]
    python demo/schedule_demo.py --link --event "office hours"
    python demo/schedule_demo.py --book --event "office hours" \
        --slot 2026-10-02T18:00:00Z --name "Your Name" --email you@example.com
    python demo/schedule_demo.py --upcoming [--days 30]
    python demo/schedule_demo.py --cancel https://api.calendly.com/scheduled_events/XXXX
"""

import argparse
import sys

import calendly_tools as cal


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="list active event types")
    ap.add_argument("--slots", action="store_true", help="show available times")
    ap.add_argument("--link", action="store_true", help="create a single-use booking link")
    ap.add_argument("--book", action="store_true", help="create a booking")
    ap.add_argument("--upcoming", action="store_true", help="list upcoming events")
    ap.add_argument("--cancel", metavar="EVENT_URI", help="cancel a scheduled event")
    ap.add_argument("--event", default="office hours", help="event type name substring")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--slot", help="slot start time (ISO, e.g. 2026-10-02T18:00:00Z)")
    ap.add_argument("--name", default="Demo Student")
    ap.add_argument("--email", default="demo@example.com")
    ap.add_argument("--tz", default="America/New_York")
    args = ap.parse_args()

    if args.list:
        user = cal.me()
        print(f"user: {user['name']} <{user['email']}>")
        for e in cal.event_types(user["uri"]):
            print(f"- {e['name']}  ({e['duration']} min)\n    {e['uri']}")
        return

    if args.slots:
        et = cal.find_event_type(args.event)
        print(f"event: {et['name']}")
        slots = cal.available_times(et["uri"], days=args.days)
        if not slots:
            print("  (no available times)")
        for s in slots:
            print(f"  {s['start_time']}  ({cal.pretty(s['start_time'], args.tz)})")
        return

    if args.link:
        et = cal.find_event_type(args.event)
        print(cal.single_use_link(et["uri"]))
        return

    if args.book:
        if not args.slot:
            sys.exit("--book needs --slot")
        et = cal.find_event_type(args.event)
        kind = cal.location_kind(et["uri"])
        invitee = cal.book(et["uri"], args.slot, args.name, args.email, args.tz, kind)
        print(f"booked: {cal.pretty(args.slot, args.tz)}")
        print(f"  event:      {invitee['event']}")
        print(f"  cancel_url: {invitee['cancel_url']}")
        return

    if args.upcoming:
        user = cal.me()
        for e in cal.upcoming(user["uri"], days=args.days):
            print(f"- {e['start_time']}  {e['name']}  {e['uri']}")
        return

    if args.cancel:
        cal.cancel(args.cancel)
        print("cancelled")
        return

    ap.print_help()


if __name__ == "__main__":
    main()
