#!/usr/bin/env python3
"""content-cartridge: insert a cartridge (one content pillar), press START, get the week.

  python3 cartridge.py build cartridges/<slug>.json --out out/ [--motif analog|cyberpunk|y2k-blog]
                       [--start YYYY-MM-DD] [--seed N] [--style style.json] [--png]
  python3 cartridge.py check cartridges/<slug>.json

A cartridge is a small JSON file in her own words: the pillar, who it is for, the promise,
five to seven post ideas (hook, body beats, format), a reel shot list and a CTA line.
This module holds the pure parts: schema checks, the week layout, week.ics and week.md.
render.py draws the page.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
import sys
from pathlib import Path

SCHEMA = "content-cartridge/1"
FORMATS = ("reel", "carousel", "post", "story", "live", "email")
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
REST_ORDER = (6, 3)  # with fewer than 7 posts, Sunday rests first, then Wednesday
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LIMITS = {"name": 40, "audience": 160, "promise": 200, "cta": 160, "title": 60, "hook": 180,
          "beat": 200, "shot": 120, "note": 160, "story": 400}


# ---------- schema ----------

def _text(errors: list, where: str, value: object, limit: int, required: bool = True) -> None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            errors.append(f"{where} is missing. Add a line in your own words.")
        return
    if not isinstance(value, str):
        errors.append(f"{where} should be text in quotes.")
    elif len(value) > limit:
        errors.append(f"{where} is {len(value)} characters. Keep it under {limit} so it fits the screen.")


def validate(cart: object) -> list[str]:
    """Every problem with a cartridge, in plain words. An empty list means it plays."""
    if not isinstance(cart, dict):
        return ["The cartridge should be one JSON object, starting with { and ending with }."]
    errors: list[str] = []
    if cart.get("schema") not in (None, SCHEMA):
        errors.append(f"schema should be \"{SCHEMA}\".")
    slug = cart.get("slug")
    if not isinstance(slug, str) or not SLUG.match(slug):
        errors.append("slug should be lowercase words joined by hyphens, like \"behind-the-kiln\".")
    for key in ("name", "audience", "promise", "cta"):
        _text(errors, key, cart.get(key), LIMITS[key])
    posts = cart.get("posts")
    if not isinstance(posts, list) or not 5 <= len(posts) <= 7:
        count = len(posts) if isinstance(posts, list) else 0
        errors.append(f"posts should hold 5 to 7 post ideas. This cartridge has {count}.")
        posts = posts if isinstance(posts, list) else []
    for i, post in enumerate(posts, 1):
        where = f"post {i}"
        if not isinstance(post, dict):
            errors.append(f"{where} should be an object with title, hook, beats and format.")
            continue
        _text(errors, f"{where} title", post.get("title"), LIMITS["title"])
        _text(errors, f"{where} hook", post.get("hook"), LIMITS["hook"])
        if post.get("format") not in FORMATS:
            errors.append(f"{where} format should be one of: {', '.join(FORMATS)}.")
        beats = post.get("beats")
        if not isinstance(beats, list) or not 1 <= len(beats) <= 6:
            errors.append(f"{where} beats should be a list of 1 to 6 short lines.")
        else:
            for j, beat in enumerate(beats, 1):
                _text(errors, f"{where} beat {j}", beat, LIMITS["beat"])
    shots = cart.get("shot_list")
    if not isinstance(shots, list) or not 1 <= len(shots) <= 10:
        errors.append("shot_list should hold 1 to 10 shots for the reel.")
    else:
        for i, shot in enumerate(shots, 1):
            if not isinstance(shot, dict):
                errors.append(f"shot {i} should be an object with shot and note.")
                continue
            _text(errors, f"shot {i}", shot.get("shot"), LIMITS["shot"])
            _text(errors, f"shot {i} note", shot.get("note"), LIMITS["note"], required=False)
    stories = cart.get("stories", [])
    if not isinstance(stories, list) or len(stories) > 5:
        errors.append("stories, if you keep them, should be a list of up to 5 short stories.")
    else:
        for i, story in enumerate(stories, 1):
            _text(errors, f"story {i}", story, LIMITS["story"])
    return errors


def load_cartridge(path: Path) -> dict:
    try:
        cart = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"Could not open the cartridge {path} ({exc.strerror}). Check the file name.")
    except ValueError as exc:
        raise SystemExit(f"The cartridge {path} is not valid JSON ({exc}). "
                         "A missing comma or quote is the usual cause.")
    errors = validate(cart)
    if errors:
        raise SystemExit("This cartridge needs a little care before it plays:\n  - " + "\n  - ".join(errors))
    return cart


# ---------- the week, as a pure function ----------

def next_monday(today: dt.date) -> dt.date:
    """The Monday on or after today."""
    return today + dt.timedelta(days=(7 - today.weekday()) % 7)


def post_order(n_posts: int, seed: int = 0) -> list[int]:
    """Seed 0 keeps her order. Any other seed is a fixed, repeatable shuffle."""
    order = list(range(n_posts))
    if seed:
        random.Random(seed).shuffle(order)
    return order


def layout_week(cart: dict, start: dt.date, seed: int = 0) -> list[dict]:
    """Seven days, Monday to Sunday. Each day holds one post index, or None for a rest day."""
    if start.weekday() != 0:
        raise ValueError("The week starts on a Monday.")
    n = len(cart["posts"])
    rest = set(REST_ORDER[: 7 - n])
    order = iter(post_order(n, seed))
    return [{"day": i, "date": (start + dt.timedelta(days=i)).isoformat(), "label": DAYS[i],
             "post": None if i in rest else next(order)} for i in range(7)]


def week_from_slots(start: dt.date, slots: list) -> list[dict]:
    """Rebuild a week from a list of seven post indexes (or None), as the page stores it."""
    return [{"day": i, "date": (start + dt.timedelta(days=i)).isoformat(), "label": DAYS[i], "post": p}
            for i, p in enumerate(slots)]


# ---------- week.ics ----------

def ics_escape(text: str) -> str:
    return (str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def ics_fold(line: str) -> str:
    """RFC 5545: lines longer than 75 octets continue on the next line after CRLF and a space."""
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def post_summary(post: dict) -> str:
    return f"[{post['format'].capitalize()}] {post['title']}"


def post_description(cart: dict, post: dict) -> str:
    lines = [f"Hook: {post['hook']}", ""] + [f"- {b}" for b in post["beats"]]
    lines += ["", f"CTA: {cart['cta']}", f"Pillar: {cart['name']}"]
    return "\n".join(lines)


def build_ics(cart: dict, week: list[dict], stamp: dt.datetime | None = None) -> str:
    stamp = (stamp or dt.datetime.now(dt.timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    rows = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Rocha Coded//content-cartridge//EN",
            "CALSCALE:GREGORIAN", "METHOD:PUBLISH", f"X-WR-CALNAME:{ics_escape(cart['name'])}"]
    for day in week:
        if day["post"] is None:
            continue
        post = cart["posts"][day["post"]]
        d = dt.date.fromisoformat(day["date"])
        rows += ["BEGIN:VEVENT",
                 f"UID:{cart['slug']}-{d:%Y%m%d}-{day['post']}@content-cartridge",
                 f"DTSTAMP:{stamp}",
                 f"DTSTART;VALUE=DATE:{d:%Y%m%d}",
                 f"DTEND;VALUE=DATE:{d + dt.timedelta(days=1):%Y%m%d}",
                 f"SUMMARY:{ics_escape(post_summary(post))}",
                 f"DESCRIPTION:{ics_escape(post_description(cart, post))}",
                 f"CATEGORIES:{ics_escape(cart['name'])}",
                 "TRANSP:TRANSPARENT",
                 "END:VEVENT"]
    rows.append("END:VCALENDAR")
    return "\r\n".join(ics_fold(r) for r in rows) + "\r\n"


# ---------- week.md ----------

def build_md(cart: dict, week: list[dict]) -> str:
    first, last = week[0]["date"], week[-1]["date"]
    out = [f"# {cart['name']}: the week of {first}", "",
           f"For: {cart['audience']}", f"Promise: {cart['promise']}", f"CTA: {cart['cta']}", ""]
    for day in week:
        d = dt.date.fromisoformat(day["date"])
        heading = f"## {DAY_NAMES[day['day']]} {d.day} {d:%b}"
        if day["post"] is None:
            out += [heading, "", "Rest day. Reply to comments, save ideas, live your life.", ""]
            continue
        post = cart["posts"][day["post"]]
        out += [f"{heading}: {post['title']} ({post['format']})", "", f"**Hook:** {post['hook']}", ""]
        out += [f"- {b}" for b in post["beats"]] + [""]
    out += ["## Reel shot list", ""]
    out += [f"{i}. {s['shot']}" + (f" ({s['note']})" if s.get("note") else "")
            for i, s in enumerate(cart["shot_list"], 1)]
    out += ["", f"Week ends {last}. Made with content-cartridge.", ""]
    return "\n".join(out)


# ---------- command line ----------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cartridge.py", description="Insert a cartridge, press START, get the week.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="render the handheld page, week.ics and week.md")
    b.add_argument("cartridge", type=Path)
    b.add_argument("--out", type=Path, default=Path("out"))
    b.add_argument("--motif", choices=("analog", "cyberpunk", "y2k-blog"), default=None)
    b.add_argument("--start", help="any date; the week starts on the Monday on or after it")
    b.add_argument("--seed", type=int, default=0, help="0 keeps your order; any other number shuffles")
    b.add_argument("--style", type=Path, default=None, help="a style.json to use")
    b.add_argument("--png", action="store_true", help="also save a picture of the page (needs Chrome)")
    c = sub.add_parser("check", help="check a cartridge and say what needs fixing")
    c.add_argument("cartridge", type=Path)
    args = ap.parse_args(argv)

    cart = load_cartridge(args.cartridge)
    if args.cmd == "check":
        print(f"READY: {cart['name']} plays. {len(cart['posts'])} posts, {len(cart['shot_list'])} shots.")
        return 0

    import render  # local import keeps the pure parts above free of page code
    try:
        start = next_monday(dt.date.fromisoformat(args.start) if args.start else dt.date.today())
    except ValueError:
        raise SystemExit(f"--start should be a date like 2026-11-02, not {args.start!r}.")
    week = layout_week(cart, start, args.seed)
    style = render.load_style(render.find_style(args.style))
    motif = render.resolve_motif(args.motif, style)
    args.out.mkdir(parents=True, exist_ok=True)
    page = args.out / f"{cart['slug']}.html"
    page.write_text(render.render_page(cart, week, style, motif, seed=args.seed), encoding="utf-8")
    (args.out / "week.ics").write_text(build_ics(cart, week), encoding="utf-8", newline="")
    (args.out / "week.md").write_text(build_md(cart, week), encoding="utf-8")
    print(f"READY: {cart['name']} is inserted ({motif}), week of {start.isoformat()}.")
    print(f"Page: {page}\nCalendar: {args.out / 'week.ics'}\nNotes: {args.out / 'week.md'}")
    if args.png:
        ok, msg = render.render_png(page, args.out / f"{cart['slug']}.png", 1080, 1600)
        print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
