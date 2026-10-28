"""Rendering for content-cartridge: style.json, the three motif skins, and Chrome pictures.

One function, render_page(), draws the same cartridge week in three motif families:
  cyberpunk  the handheld: plum shell, cream screen, candy buttons, gold screws (the default)
  analog     a printed cartridge insert booklet you could hold
  y2k-blog   the handheld inside a cream OS 9 window with a blog sidebar
Motif is structure; style.json palette and fonts are colour and type, so every family re-tones.
Python renders every fragment. The page script only moves fragments between days.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
CSS_FILES = {"cyberpunk": ["handheld.css"], "analog": ["handheld.css", "motif-analog.css"],
             "y2k-blog": ["handheld.css", "motif-y2k.css"]}
STYLE_EXAMPLE = HERE / "examples" / "style.rocha-coded.json"
REPO_ISSUES = "https://github.com/RochaStone/content-cartridge/issues"
MOTIFS = ("cyberpunk", "analog", "y2k-blog")
MOTIF_ALIASES = {"guest-check": "analog", "front-page": "analog", "magazine-scrawl": "analog",
                 "pink-paper": "analog", "rotary": "analog", "leopard": "analog", "neutral": "analog",
                 "retro-tv": "cyberpunk", "handheld": "cyberpunk", "sticker-collage": "y2k-blog",
                 "y2k": "y2k-blog", "blog": "y2k-blog"}
COLOUR = re.compile(r"^#[0-9A-Fa-f]{3,8}$")
FONT_NAME = re.compile(r"^[A-Za-z0-9 ]{1,40}$")
PALETTE_VARS = {"hero": "--ground", "plum": "--plum", "wine": "--wine", "accent": "--candy",
                "paper": "--cream", "paper_pink": "--blush", "ink": "--ink", "marker": "--marker",
                "gold": "--gold"}
FONT_VARS = {
    "masthead": ("--display", 'Georgia, "Times New Roman", serif', "opsz,wght@9..144,400;9..144,900"),
    "label": ("--label", 'system-ui, "Helvetica Neue", Arial, sans-serif', "wght@400;800"),
    "body": ("--body", 'Georgia, "Times New Roman", serif', ""),
    "mono": ("--mono", "ui-monospace, Menlo, Consolas, monospace", "wght@400;500"),
    "scrawl": ("--scrawl", '"Marker Felt", "Comic Sans MS", cursive', ""),
    "pixel": ("--pixel", '"Pixelify Sans", ui-monospace, monospace', ""),
}
HOUSE_PIXEL_FONT = "Silkscreen"
FORMAT_CODES = {"reel": "RL", "carousel": "CA", "post": "PO", "story": "ST", "live": "LV", "email": "EM"}
DAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
PIXEL_HEART = ('<svg class="pix" viewBox="0 0 7 6" width="14" height="12" aria-hidden="true" shape-rendering="crispEdges">'
               '<path fill="currentColor" d="M1 0h2v1h1V0h2v1h1v2H6v1H5v1H4v1H3V5H2V4H1V3H0V1h1z"/></svg>')
PIXEL_STAR = ('<svg class="pix" viewBox="0 0 5 5" width="12" height="12" aria-hidden="true" shape-rendering="crispEdges">'
              '<path fill="currentColor" d="M2 0h1v2h2v1H3v2H2V3H0V2h2z"/></svg>')


def _e(s: object) -> str:
    return html.escape(str(s), quote=True)


# ---------- style.json (the shared Rocha Coded rules) ----------

def find_style(explicit: Path | None = None, cwd: Path | None = None, home: Path | None = None) -> Path:
    """--style, then ./style.json, then ~/.rocha-coded/style.json, then the bundled example."""
    candidates = [explicit] if explicit else []
    candidates += [Path(cwd or Path.cwd()) / "style.json",
                   Path(home or Path.home()) / ".rocha-coded" / "style.json", STYLE_EXAMPLE]
    return next((Path(c) for c in candidates if c and Path(c).is_file()), STYLE_EXAMPLE)


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"Could not read style file {path} ({exc}). Using the bundled example look.", file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def load_style(path: Path | None = None) -> dict:
    path = Path(path or STYLE_EXAMPLE)
    if path.resolve() == STYLE_EXAMPLE.resolve():
        return _read_json(STYLE_EXAMPLE)
    user = _read_json(path)
    return inherit_style(user) if user else _read_json(STYLE_EXAMPLE)


def inherit_style(user: dict) -> dict:
    """A user's style borrows ONLY missing palette and font entries from the bundled example.
    Lines, owner, handle, name, references and notes never fall back to Rocha's."""
    example = _read_json(STYLE_EXAMPLE)
    merged = dict(user)
    for key in ("palette", "fonts"):
        mine = user.get(key) if isinstance(user.get(key), dict) else {}
        base = example.get(key) if isinstance(example.get(key), dict) else {}
        merged[key] = {**base, **{k: v for k, v in mine.items() if str(v or "").strip()}}
    return merged


def resolve_motif(requested: str | None, style: dict) -> str:
    """--motif wins, then style.json motif, then cyberpunk (the handheld). Old names map to a family."""
    raw = str(requested or style.get("motif") or "cyberpunk").strip().lower()
    raw = MOTIF_ALIASES.get(raw, raw)
    return raw if raw in MOTIFS else "cyberpunk"


def style_head(style: dict, motif: str) -> str:
    palette = style.get("palette") if isinstance(style.get("palette"), dict) else {}
    fonts = dict(style.get("fonts")) if isinstance(style.get("fonts"), dict) else {}
    if not str(fonts.get("pixel") or "").strip():
        fonts["pixel"] = HOUSE_PIXEL_FONT
    css_vars, links = [], []
    for key, var in PALETTE_VARS.items():
        val = str(palette.get(key) or "").strip()
        if COLOUR.match(val):
            css_vars.append(f"{var}: {val};")
    seen = set()
    for key, (var, fallback, axes) in FONT_VARS.items():
        fam = str(fonts.get(key) or "").strip()
        if not FONT_NAME.match(fam):
            continue
        css_vars.append(f'{var}: "{fam}", {fallback};')
        q = fam.replace(" ", "+")
        if axes:
            links.append(f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={q}:{axes}&display=swap">')
        if fam not in seen:
            links.append(f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={q}&display=swap">')
            seen.add(fam)
    return "\n".join(links) + f"\n<style>:root {{ {' '.join(css_vars)} }}</style>"


def _lines(style: dict) -> dict:
    lines = style.get("lines") if isinstance(style.get("lines"), dict) else {}
    return {k: str(lines.get(k) or "").strip() for k in ("scrawl", "stamp")}


def _credit(style: dict) -> str:
    return " · ".join(str(x).strip() for x in (style.get("owner"), style.get("handle"), "made with Rocha Coded")
                      if x and str(x).strip())


# ---------- fragments (one per post, per place it can appear) ----------

def _date(iso: str) -> dt.date:
    return dt.date.fromisoformat(iso)


def frag_row(post: dict | None) -> str:
    if post is None:
        return '<span class="fmt rest">ZZ</span><span class="ttl">rest day</span>'
    return f'<span class="fmt">{FORMAT_CODES[post["format"]]}</span><span class="ttl">{_e(post["title"])}</span>'


def frag_sheet(post: dict | None) -> str:
    if post is None:
        return '<p class="s-title rest">Rest day</p><p class="s-hook">Reply to comments, save ideas, live your life.</p>'
    beats = "".join(f"<li>{_e(b)}</li>" for b in post["beats"])
    return (f'<p class="s-title">{_e(post["title"])} <span class="pill">{_e(post["format"])}</span></p>'
            f'<p class="s-hook">{_e(post["hook"])}</p><ul class="s-beats">{beats}</ul>')


def frag_manual(post: dict | None) -> str:
    if post is None:
        return ('<h3 class="m-title">Rest day</h3><p class="m-hook">Nothing to post. '
                'Reply to comments, save ideas, live your life.</p>')
    beats = "".join(f"<li>{_e(b)}</li>" for b in post["beats"])
    return (f'<p class="m-fmt"><span class="pill">{_e(post["format"])}</span></p>'
            f'<h3 class="m-title">{_e(post["title"])}</h3>'
            f'<p class="m-hook"><b>Hook.</b> {_e(post["hook"])}</p><ol class="m-beats">{beats}</ol>')


def _templates(cart: dict) -> str:
    out = []
    for k, post in enumerate([*cart["posts"], None]):
        key = "rest" if post is None else str(k)
        out.append(f'<template id="t-row-{key}">{frag_row(post)}</template>'
                   f'<template id="t-sheet-{key}">{frag_sheet(post)}</template>'
                   f'<template id="t-man-{key}">{frag_manual(post)}</template>')
    return "\n".join(out)


# ---------- the pieces ----------

def _post(cart: dict, idx: int | None) -> dict | None:
    return None if idx is None else cart["posts"][idx]


def handheld(cart: dict, week: list[dict], style: dict) -> str:
    lines = _lines(style)
    logo = _e(str(style.get("name") or "").strip() or "content cartridge")
    rows = "".join(
        f'<li class="row{" sel" if i == 0 else ""}" data-day="{i}"><span class="d">{DAYS[i]}</span>'
        f'<span class="dt">{_date(day["date"]).day:02d}</span><span class="slot">{frag_row(_post(cart, day["post"]))}</span>'
        f'<span class="chk" aria-hidden="true"></span></li>' for i, day in enumerate(week))
    scrawl = f'<i class="cart-scrawl">{_e(lines["scrawl"])}</i>' if lines["scrawl"] else ""
    return f"""<section class="handheld" aria-label="Content cartridge handheld">
  <div class="cart" aria-hidden="true"><div class="cart-ridges"></div>
    <div class="cart-label"><span class="cart-kicker">content cartridge</span><b>{_e(cart["name"])}</b>{scrawl}</div></div>
  <div class="shell">
    <span class="screw tl"></span><span class="screw tr"></span>
    <div class="bezel">
      <div class="bezel-top"><span class="led" aria-hidden="true"></span><span>power</span><span class="bezel-rule"></span></div>
      <div class="screen" id="screen" tabindex="0" aria-label="Screen. Arrow keys move, A marks done, B swaps, Enter is START.">
        <div class="boot px">
          <p class="boot-k">cartridge in</p>
          <p class="boot-t">{_e(cart["name"])}</p>
          <p class="boot-start"><span class="blink">press start</span></p>
        </div>
        <div class="weekview px" hidden>
          <p class="wk-head"><span>{_e(cart["name"])}</span><span class="wk-date">wk {_date(week[0]["date"]):%d %b}</span></p>
          <ol class="week">{rows}</ol>
          <p class="status" aria-live="polite">A done · B swap · SEL shuffle</p>
        </div>
      </div>
      <p class="bezel-bottom">week of {_date(week[0]["date"]):%a %d %b %Y}</p>
    </div>
    <p class="logo">{logo}<span>handheld</span></p>
    <div class="controls">
      <div class="dpad" role="group" aria-label="Direction pad">
        <button class="up" data-k="up" aria-label="Up"></button><button class="left" data-k="left" aria-label="Left"></button>
        <span class="mid"></span>
        <button class="right" data-k="right" aria-label="Right"></button><button class="down" data-k="down" aria-label="Down"></button>
      </div>
      <div class="ab">
        <span class="ab-cell"><button class="btn b" data-k="b" aria-label="B, swap days">B</button><small>swap</small></span>
        <span class="ab-cell"><button class="btn a" data-k="a" aria-label="A, mark done">A</button><small>done</small></span>
      </div>
    </div>
    <div class="pills">
      <span class="pill-cell"><button data-k="select" aria-label="Select, shuffle the week"></button><small>select</small></span>
      <span class="pill-cell"><button data-k="start" aria-label="Start, lay out the week"></button><small>start</small></span>
      <span class="pill-cell"><button data-k="save" class="cream" aria-label="Save week.ics and week.md"></button><small>save</small></span>
      <span class="pill-cell"><button data-k="print" class="cream" aria-label="Print the week sheet"></button><small>print</small></span>
    </div>
    <div class="grille" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></div>
  </div>
</section>"""


def manual(cart: dict, week: list[dict]) -> str:
    shots = "".join(f'<li><b>{_e(s["shot"])}</b>' + (f'<span>{_e(s["note"])}</span>' if s.get("note") else "") + "</li>"
                    for s in cart["shot_list"])
    first = _date(week[0]["date"])
    return f"""<section class="manual" aria-label="Cartridge manual">
  <p class="m-kicker" id="m-day">MON {first.day:02d} {first:%b}</p>
  <div id="m-detail">{frag_manual(_post(cart, week[0]["post"]))}</div>
  <p class="m-cta"><b>CTA.</b> {_e(cart["cta"])}</p>
  <details class="m-more" open><summary>Reel shot list</summary><ol class="m-shots">{shots}</ol></details>
  <details class="m-more"><summary>This cartridge</summary>
    <p><b>For.</b> {_e(cart["audience"])}</p><p><b>Promise.</b> {_e(cart["promise"])}</p></details>
</section>"""


def sheet(cart: dict, week: list[dict], style: dict, analog: bool) -> str:
    lines, first, last = _lines(style), _date(week[0]["date"]), _date(week[-1]["date"])
    rows = "".join(
        f'<li class="s-row" data-day="{i}"><button class="box" data-k="done" data-day="{i}" aria-label="Mark {DAYS[i]} done"></button>'
        f'<span class="s-day">{DAYS[i]}<b>{_date(day["date"]).day:02d}</b></span>'
        f'<div class="s-slot">{frag_sheet(_post(cart, day["post"]))}</div></li>' for i, day in enumerate(week))
    shots = "".join(f'<li>{_e(s["shot"])}' + (f' <span>{_e(s["note"])}</span>' if s.get("note") else "") + "</li>"
                    for s in cart["shot_list"])
    stamp = f'<span class="stamp">{_e(lines["stamp"])}</span>' if lines["stamp"] else ""
    scrawl = f'<p class="s-scrawl">{_e(lines["scrawl"])}</p>' if lines["scrawl"] else ""
    tools = ('<nav class="toolbar" aria-label="Booklet tools"><button data-k="select">shuffle</button>'
             '<button data-k="save">save .ics + .md</button><button data-k="print">print</button></nav>') if analog else ""
    return f"""<section class="sheet" aria-label="Cartridge insert">
  {tools}
  <header class="s-label">
    <div class="s-cart"><span class="s-kicker">cartridge insert · week of {first:%d %b} to {last:%d %b %Y}</span>
      <h1>{_e(cart["name"])}</h1>
      <p class="s-for"><b>for</b> {_e(cart["audience"])}</p>
      <p class="s-promise">{_e(cart["promise"])}</p>{scrawl}</div>{stamp}
  </header>
  <ol class="s-week">{rows}</ol>
  <div class="s-foot">
    <div class="s-shots"><h2>Reel shot list</h2><ol>{shots}</ol></div>
    <div class="s-cta"><h2>CTA</h2><p>{_e(cart["cta"])}</p><p class="s-credit">{_e(_credit(style))}</p></div>
  </div>
</section>"""


def y2k_window(cart: dict, week: list[dict], inner: str) -> str:
    first = _date(week[0]["date"])
    n_posts = sum(1 for d in week if d["post"] is not None)
    return f"""<main class="win" aria-label="content-cartridge window">
  <div class="titlebar"><span class="btns"><i></i><i></i><i></i></span><span class="title px">content-cartridge.exe</span></div>
  <div class="marquee"><span>{PIXEL_STAR} now playing: {_e(cart["name"])} {PIXEL_STAR} {n_posts} posts this week {PIXEL_STAR} last updated {first:%d %b %Y} {PIXEL_STAR}</span></div>
  <div class="winbody">
    <div class="post">{inner}</div>
    <aside class="side">
      <section><h3 class="px">about me</h3><p>{_e(cart["audience"])}</p></section>
      <section><h3 class="px">mood</h3><p>pressing start ✧</p></section>
      <section><h3 class="px">now playing</h3><p>{_e(cart["name"])}</p></section>
      <section class="counter"><h3 class="px">hit counter</h3><p>you are visitor no.<br><b>000,777</b></p></section>
      <section class="guest"><h3 class="px">guestbook</h3><p><a href="{REPO_ISSUES}">sign my guestbook</a> {PIXEL_HEART}</p></section>
      <p class="sparkle">{PIXEL_HEART}{PIXEL_STAR}{PIXEL_HEART}</p>
      <p class="updated">last updated {first:%d %b %Y}</p>
    </aside>
  </div>
</main>"""


def page_data(cart: dict, week: list[dict], seed: int) -> dict:
    """What the page script needs: the posts (for week.ics and week.md) and the starting slots."""
    return {"slug": cart["slug"], "name": cart["name"], "audience": cart["audience"], "promise": cart["promise"],
            "cta": cart["cta"], "posts": cart["posts"], "shot_list": cart["shot_list"],
            "start": week[0]["date"], "slots": [d["post"] for d in week], "seed": seed}


def render_page(cart: dict, week: list[dict], style: dict | None = None, motif: str | None = None,
                seed: int = 0) -> str:
    style = load_style() if style is None else style
    motif = resolve_motif(motif, style)
    hh = handheld(cart, week, style)
    if motif == "analog":
        body = sheet(cart, week, style, analog=True)
    else:
        play = f'<div class="play">{hh}{manual(cart, week)}</div>'
        body = (y2k_window(cart, week, play) if motif == "y2k-blog" else play) + sheet(cart, week, style, analog=False)
    css = "\n".join((ASSETS / f).read_text(encoding="utf-8") for f in CSS_FILES[motif])
    js = (ASSETS / "handheld.js").read_text(encoding="utf-8")
    data = json.dumps(page_data(cart, week, seed), ensure_ascii=False).replace("<", "\\u003c")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(cart["name"])} · content cartridge</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<style>{css}</style>
{style_head(style, motif)}</head>
<body class="m-{motif}">
{body}
{_templates(cart)}
<script type="application/json" id="cart-data">{data}</script>
<script>{js}</script>
</body></html>"""


# ---------- Chrome ----------

def find_chrome() -> str | None:
    env = os.environ.get("CHROME_PATH")
    if env and Path(env).exists():
        return env
    for cmd in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "microsoft-edge"):
        p = shutil.which(cmd)
        if p:
            return p
    for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"):
        if Path(p).exists():
            return p
    return None


def png_size(path: Path) -> tuple[int, int]:
    with Path(path).open("rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    return struct.unpack(">II", head[16:24])


def run_chrome(args: list[str], timeout: int = 90) -> subprocess.CompletedProcess | None:
    """Run headless Chrome with a throwaway profile. None when there is no Chrome or it fails to start."""
    chrome = find_chrome()
    if not chrome:
        return None
    with tempfile.TemporaryDirectory() as profile:
        cmd = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
               "--no-default-browser-check", f"--user-data-dir={profile}", *args]
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            cmd.insert(1, "--no-sandbox")
        try:
            return subprocess.run(cmd, capture_output=True, timeout=timeout, check=False, text=True)
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"Chrome could not run ({exc}).", file=sys.stderr)
            return None


def render_png(page_html: Path, png: Path, width: int = 1080, height: int = 1600,
               fragment: str = "play-still") -> tuple[bool, str]:
    if not find_chrome():
        return False, ("No Chrome or Chromium found, so no picture this time. Your page, week.ics and week.md "
                       "are ready. Install Chrome, or set CHROME_PATH, then run again with --png.")
    png = Path(png).resolve()
    run_chrome([f"--window-size={width},{height}", "--force-device-scale-factor=1",
                "--virtual-time-budget=8000", f"--screenshot={png}", Path(page_html).resolve().as_uri() + (f"#{fragment}" if fragment else "")])
    if not png.exists():
        return False, "Chrome ran but saved no picture. Your page, week.ics and week.md are ready."
    w, h = png_size(png)
    return True, f"Picture: {png.name} ({w}x{h})"
