"""Tests for content-cartridge. Run from the repo root: python3 -m unittest discover -s tests -v"""
from __future__ import annotations

import copy
import datetime as dt
import html
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import cartridge  # noqa: E402
import render  # noqa: E402

SAMPLES = sorted((ROOT / "cartridges").glob("*.json"))
MONDAY = dt.date(2026, 11, 2)
STAMP = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


def sample(name: str = "behind-the-kiln") -> dict:
    return json.loads((ROOT / "cartridges" / f"{name}.json").read_text(encoding="utf-8"))


# ---------- a tiny RFC 5545 parser, enough to prove the file is well formed ----------

def parse_ics(text: str) -> dict:
    assert "\n" not in text.replace("\r\n", ""), "every line must end in CRLF"
    raw = text.split("\r\n")
    assert raw[-1] == "", "file must end with CRLF"
    for line in raw[:-1]:
        assert len(line.encode("utf-8")) <= 75, f"line longer than 75 octets: {line!r}"
    lines: list[str] = []
    for line in raw[:-1]:
        if line.startswith(" "):
            lines[-1] += line[1:]
        else:
            lines.append(line)
    root: dict = {"name": "ROOT", "props": [], "children": []}
    stack = [root]
    for line in lines:
        m = re.match(r"^([A-Z][A-Z0-9-]*)((?:;[A-Z-]+=[^:;]+)*):(.*)$", line)
        assert m, f"not a content line: {line!r}"
        name, params, value = m.groups()
        if name == "BEGIN":
            comp = {"name": value, "props": [], "children": []}
            stack[-1]["children"].append(comp)
            stack.append(comp)
        elif name == "END":
            assert stack[-1]["name"] == value, f"END:{value} closes {stack[-1]['name']}"
            stack.pop()
        else:
            stack[-1]["props"].append((name, params, value))
    assert len(stack) == 1, "unclosed component"
    assert [c["name"] for c in root["children"]] == ["VCALENDAR"]
    return root["children"][0]


def props(comp: dict) -> dict:
    return {n: v for n, _, v in comp["props"]}


def unescape(v: str) -> str:
    return re.sub(r"\\(.)", lambda m: "\n" if m.group(1) in "nN" else m.group(1), v)


class Schema(unittest.TestCase):
    def test_samples_are_valid(self):
        self.assertEqual(len(SAMPLES), 3)
        for path in SAMPLES:
            with self.subTest(path.name):
                cart = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(cartridge.validate(cart), [])
                self.assertEqual(cart["slug"], path.stem)

    def test_post_count_bounds(self):
        cart = sample("money-mornings")
        self.assertEqual(len(cart["posts"]), 7)
        too_many = copy.deepcopy(cart)
        too_many["posts"].append(cart["posts"][0])
        self.assertTrue(any("5 to 7" in e for e in cartridge.validate(too_many)))
        too_few = copy.deepcopy(cart)
        too_few["posts"] = cart["posts"][:4]
        self.assertTrue(any("5 to 7" in e for e in cartridge.validate(too_few)))

    def test_problems_are_named_plainly(self):
        cart = sample()
        cart["slug"] = "Behind The Kiln"
        cart["cta"] = ""
        cart["posts"][1]["format"] = "podcast"
        cart["posts"][2]["beats"] = []
        cart["posts"][3]["hook"] = "x" * 400
        cart["shot_list"] = [{"note": "no shot"}]
        errors = cartridge.validate(cart)
        joined = "\n".join(errors)
        for needle in ("slug", "cta is missing", "post 2 format", "post 3 beats", "post 4 hook is 400", "shot 1 is missing"):
            self.assertIn(needle, joined)

    def test_not_an_object(self):
        self.assertTrue(cartridge.validate([1, 2]))
        self.assertTrue(cartridge.validate({"posts": "many"}))

    def test_load_reports_bad_json_kindly(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "broken.json"
            p.write_text('{"name": "x",}', encoding="utf-8")
            with self.assertRaises(SystemExit) as cm:
                cartridge.load_cartridge(p)
            self.assertIn("not valid JSON", str(cm.exception))


class WeekLayout(unittest.TestCase):
    def test_seven_posts_fill_the_week(self):
        week = cartridge.layout_week(sample("money-mornings"), MONDAY)
        self.assertEqual([d["post"] for d in week], list(range(7)))
        self.assertEqual([d["label"] for d in week], list(cartridge.DAYS))
        self.assertEqual(week[0]["date"], "2026-11-02")
        self.assertEqual(week[6]["date"], "2026-11-08")

    def test_rest_days(self):
        six = cartridge.layout_week(sample("behind-the-kiln"), MONDAY)
        self.assertIsNone(six[6]["post"])
        self.assertEqual([d["post"] for d in six[:6]], list(range(6)))
        five = cartridge.layout_week(sample("studio-rituals"), MONDAY)
        self.assertEqual([i for i, d in enumerate(five) if d["post"] is None], [3, 6])

    def test_seed_is_a_repeatable_permutation(self):
        cart = sample("money-mornings")
        a = [d["post"] for d in cartridge.layout_week(cart, MONDAY, seed=7)]
        b = [d["post"] for d in cartridge.layout_week(cart, MONDAY, seed=7)]
        self.assertEqual(a, b)
        self.assertEqual(sorted(a), list(range(7)))
        self.assertNotEqual(a, list(range(7)))

    def test_pure(self):
        cart = sample()
        before = json.dumps(cart, sort_keys=True)
        cartridge.layout_week(cart, MONDAY, seed=3)
        self.assertEqual(json.dumps(cart, sort_keys=True), before)

    def test_week_starts_monday(self):
        with self.assertRaises(ValueError):
            cartridge.layout_week(sample(), dt.date(2026, 11, 3))
        self.assertEqual(cartridge.next_monday(dt.date(2026, 10, 28)), MONDAY)
        self.assertEqual(cartridge.next_monday(MONDAY), MONDAY)

    def test_month_rollover(self):
        week = cartridge.layout_week(sample(), dt.date(2026, 12, 28))
        self.assertEqual(week[-1]["date"], "2027-01-03")


class Ics(unittest.TestCase):
    def test_valid_calendar_one_event_per_post(self):
        for path in SAMPLES:
            with self.subTest(path.name):
                cart = json.loads(path.read_text(encoding="utf-8"))
                week = cartridge.layout_week(cart, MONDAY)
                cal = parse_ics(cartridge.build_ics(cart, week, STAMP))
                p = props(cal)
                self.assertEqual(p["VERSION"], "2.0")
                self.assertTrue(p["PRODID"])
                events = [c for c in cal["children"] if c["name"] == "VEVENT"]
                self.assertEqual(len(events), len(cart["posts"]))
                uids = set()
                for ev, day in zip(events, [d for d in week if d["post"] is not None]):
                    e = props(ev)
                    for key in ("UID", "DTSTAMP", "DTSTART", "DTEND", "SUMMARY"):
                        self.assertIn(key, e)
                    uids.add(e["UID"])
                    self.assertEqual(e["DTSTAMP"], "20260101T000000Z")
                    self.assertEqual(e["DTSTART"], day["date"].replace("-", ""))
                    start = dt.datetime.strptime(e["DTSTART"], "%Y%m%d").date()
                    end = dt.datetime.strptime(e["DTEND"], "%Y%m%d").date()
                    self.assertEqual(end - start, dt.timedelta(days=1))
                    post = cart["posts"][day["post"]]
                    self.assertEqual(unescape(e["SUMMARY"]), cartridge.post_summary(post))
                    self.assertEqual(unescape(e["DESCRIPTION"]), cartridge.post_description(cart, post))
                self.assertEqual(len(uids), len(events))

    def test_escaping_and_folding_round_trip(self):
        cart = sample()
        cart["posts"][0]["title"] = "Commas, semicolons; back\\slash"
        cart["posts"][0]["hook"] = "Ünïcödé ✧ " * 20
        week = cartridge.layout_week(cart, MONDAY)
        cal = parse_ics(cartridge.build_ics(cart, week, STAMP))
        first = props([c for c in cal["children"] if c["name"] == "VEVENT"][0])
        self.assertEqual(unescape(first["SUMMARY"]), "[Reel] Commas, semicolons; back\\slash")
        self.assertIn("Ünïcödé ✧ " * 20, unescape(first["DESCRIPTION"]))

    def test_parser_rejects_broken_files(self):
        good = cartridge.build_ics(sample(), cartridge.layout_week(sample(), MONDAY), STAMP)
        with self.assertRaises(AssertionError):
            parse_ics(good.replace("END:VEVENT\r\n", "", 1))
        with self.assertRaises(AssertionError):
            parse_ics(good.replace("\r\n", "\n"))


class Markdown(unittest.TestCase):
    def test_week_md(self):
        cart = sample("studio-rituals")
        md = cartridge.build_md(cart, cartridge.layout_week(cart, MONDAY))
        self.assertTrue(md.startswith("# Studio Rituals: the week of 2026-11-02"))
        self.assertEqual(md.count("\n## "), 8)  # seven days and the shot list
        self.assertEqual(md.count("Rest day."), 2)
        self.assertIn("## Monday 2 Nov: Two years back (reel)", md)


class Render(unittest.TestCase):
    def page(self, motif, cart=None, style=None):
        cart = cart or sample()
        return render.render_page(cart, cartridge.layout_week(cart, MONDAY), style or render.load_style(), motif)

    def test_three_motifs_one_path(self):
        pages = {m: self.page(m) for m in render.MOTIFS}
        cy, an, y2 = pages["cyberpunk"], pages["analog"], pages["y2k-blog"]
        self.assertIn('class="handheld"', cy)
        self.assertIn("press start", cy)
        self.assertIn("Silkscreen", cy)
        self.assertIn('class="sheet"', an)
        self.assertIn("cartridge insert", an)
        self.assertNotIn('class="handheld"', an)
        self.assertIn("content-cartridge.exe", y2)
        self.assertIn("000,777", y2)
        self.assertIn('class="handheld"', y2)
        self.assertIn("RochaStone/content-cartridge/issues", y2)
        for m, page in pages.items():
            with self.subTest(m):
                self.assertIn(f'class="m-{m}"', page)
                self.assertIn('class="sheet"', page)  # every motif can PRINT the same sheet
                self.assertIn("The bowl I kept", page)
                self.assertNotIn("text-shadow", page)
                self.assertNotIn("\u2014", page)

    def test_motif_choice(self):
        self.assertEqual(render.resolve_motif(None, {}), "cyberpunk")
        self.assertEqual(render.resolve_motif(None, {"motif": "guest-check"}), "analog")
        self.assertEqual(render.resolve_motif("y2k-blog", {"motif": "analog"}), "y2k-blog")
        self.assertEqual(render.resolve_motif("nonsense", {}), "cyberpunk")

    def test_escapes_her_words(self):
        cart = sample()
        cart["name"] = "<script>alert(1)</script>"
        cart["posts"][0]["hook"] = "</script><b>x</b>"
        page = self.page("cyberpunk", cart)
        self.assertNotIn("<script>alert", page)
        data = re.search(r'<script type="application/json" id="cart-data">(.*?)</script>', page, re.S).group(1)
        self.assertEqual(json.loads(data)["posts"][0]["hook"], "</script><b>x</b>")

    def test_style_injection_guard(self):
        style = render.load_style()
        style = {**style, "palette": {"hero": "red;}</style><script>"}, "fonts": {"masthead": "x\"; }"}}
        head = render.style_head(style, "cyberpunk")
        self.assertNotIn("<script>", head)
        self.assertNotIn('x";', head)

    def test_inheritance_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "style.json"
            p.write_text(json.dumps({"palette": {"hero": "#112233"}, "fonts": {}, "lines": {}}), encoding="utf-8")
            style = render.load_style(p)
        self.assertEqual(style["palette"]["hero"], "#112233")
        self.assertEqual(style["palette"]["accent"], "#FE9DCA")  # palette borrows
        self.assertEqual(style["fonts"]["masthead"], "Fraunces")  # fonts borrow
        for key in ("owner", "handle", "name", "references", "notes"):
            self.assertNotIn(key, style)
        page = self.page("analog", style=style)
        self.assertNotIn("build your founder world", page)
        self.assertNotIn("LORE", page)
        self.assertNotIn("@rocheverse", page)
        self.assertIn("content cartridge", self.page("cyberpunk", style=style))

    def test_bundled_example_uses_her_lines(self):
        page = self.page("analog")
        self.assertIn("build your founder world", page)
        self.assertIn('class="stamp">LORE', page)

    def test_find_style_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd, home = Path(tmp) / "work", Path(tmp) / "home"
            (home / ".rocha-coded").mkdir(parents=True)
            cwd.mkdir()
            self.assertEqual(render.find_style(None, cwd, home), render.STYLE_EXAMPLE)
            (home / ".rocha-coded" / "style.json").write_text("{}", encoding="utf-8")
            self.assertEqual(render.find_style(None, cwd, home), home / ".rocha-coded" / "style.json")
            (cwd / "style.json").write_text("{}", encoding="utf-8")
            self.assertEqual(render.find_style(None, cwd, home), cwd / "style.json")

    def test_style_files_share_keys(self):
        a = json.loads((ROOT / "style.example.json").read_text(encoding="utf-8"))
        b = json.loads(render.STYLE_EXAMPLE.read_text(encoding="utf-8"))
        self.assertEqual(set(a), set(b))
        self.assertEqual(set(a["palette"]), set(b["palette"]))
        self.assertEqual(set(a["fonts"]), set(b["fonts"]))


class Cli(unittest.TestCase):
    def test_build_writes_page_ics_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            res = subprocess.run([sys.executable, str(ROOT / "cartridge.py"), "build",
                                  str(ROOT / "cartridges" / "studio-rituals.json"), "--out", str(out),
                                  "--start", "2026-10-28", "--motif", "y2k-blog"],
                                 capture_output=True, text=True, cwd=tmp)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("READY", res.stdout)
            self.assertIn("week of 2026-11-02", res.stdout)
            self.assertIn("content-cartridge.exe", (out / "studio-rituals.html").read_text(encoding="utf-8"))
            ics = (out / "week.ics").read_bytes().decode("utf-8")
            self.assertEqual(len([c for c in parse_ics(ics)["children"] if c["name"] == "VEVENT"]), 5)
            self.assertTrue((out / "week.md").read_text(encoding="utf-8").startswith("# Studio Rituals"))

    def test_check_names_problems(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.json"
            cart = sample()
            cart["posts"] = cart["posts"][:2]
            p.write_text(json.dumps(cart), encoding="utf-8")
            res = subprocess.run([sys.executable, str(ROOT / "cartridge.py"), "check", str(p)],
                                 capture_output=True, text=True)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("5 to 7", res.stderr)


HARNESS = """<!doctype html><html><body style="margin:0">
<iframe id="f" src="{src}#selftest" width="390" height="844" style="border:0"></iframe>
<script>
document.getElementById("f").addEventListener("load", function () {{
  setTimeout(function () {{
    var d = document.getElementById("f").contentDocument, st = d.getElementById("selftest");
    var r = document.createElement("pre"); r.id = "result";
    r.textContent = JSON.stringify({{ scroll: d.documentElement.scrollWidth, client: d.documentElement.clientWidth,
      ics: st ? st.getAttribute("data-ics") : null, md: st ? st.getAttribute("data-md") : null,
      rows: d.querySelectorAll(".row").length, srows: d.querySelectorAll(".s-row").length }});
    document.body.appendChild(r);
  }}, 1500);
}});
</script></body></html>"""


@unittest.skipUnless(render.find_chrome(), "Chrome or Chromium not installed")
class Headless(unittest.TestCase):
    """Real renders in headless Chrome: 390px wide, the page script's week.ics and week.md, one printed page."""

    def harness(self, page: Path) -> dict:
        h = page.parent / f"harness-{page.stem}.html"
        h.write_text(HARNESS.format(src=page.name), encoding="utf-8")
        res = render.run_chrome(["--allow-file-access-from-files", "--virtual-time-budget=10000",
                                 "--dump-dom", h.as_uri()])
        self.assertIsNotNone(res)
        m = re.search(r'<pre id="result">(.*?)</pre>', res.stdout, re.S)
        self.assertIsNotNone(m, "harness did not report")
        return json.loads(html.unescape(m.group(1)))

    def test_all_motifs_at_390_and_js_exports_match_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            for path in SAMPLES:
                cart = json.loads(path.read_text(encoding="utf-8"))
                week = cartridge.layout_week(cart, MONDAY)
                for motif in render.MOTIFS:
                    with self.subTest(cart=path.stem, motif=motif):
                        page = Path(tmp) / f"{path.stem}-{motif}.html"
                        page.write_text(render.render_page(cart, week, render.load_style(), motif), encoding="utf-8")
                        r = self.harness(page)
                        self.assertEqual(r["client"], 390)
                        self.assertLessEqual(r["scroll"], 390, "sideways scroll at 390px")
                        self.assertEqual(r["srows"], 7)
                        self.assertEqual(r["rows"], 0 if motif == "analog" else 7)
                        self.assertEqual(r["ics"], cartridge.build_ics(cart, week, STAMP))
                        self.assertEqual(r["md"], cartridge.build_md(cart, week))

    def test_buttons_swap_mark_done_and_shuffle(self):
        script = """<script>
document.getElementById("f").addEventListener("load", function () {
  setTimeout(function () {
    var d = document.getElementById("f").contentDocument;
    function press(k) { d.querySelector('.handheld [data-k="' + k + '"]').click(); }
    function titles() { return Array.prototype.map.call(d.querySelectorAll(".row .ttl"), function (t) { return t.textContent; }); }
    var before = titles();
    press("b"); press("down"); press("b");
    var swapped = titles();
    press("a");
    var done = Array.prototype.map.call(d.querySelectorAll(".row"), function (r) { return r.classList.contains("done"); });
    var sheetDone = d.querySelectorAll(".s-row.done").length;
    var manual = d.getElementById("m-day").textContent;
    press("select");
    var shuffled = titles();
    var r = document.createElement("pre"); r.id = "result";
    r.textContent = JSON.stringify({ before: before, swapped: swapped, done: done, sheetDone: sheetDone,
                                     manual: manual, shuffled: shuffled });
    document.body.appendChild(r);
  }, 1500);
});
</script>"""
        with tempfile.TemporaryDirectory() as tmp:
            cart = sample("behind-the-kiln")
            page = Path(tmp) / "kiln.html"
            page.write_text(render.render_page(cart, cartridge.layout_week(cart, MONDAY), render.load_style(),
                                               "cyberpunk"), encoding="utf-8")
            h = Path(tmp) / "h.html"
            h.write_text('<!doctype html><html><body><iframe id="f" src="kiln.html#selftest" width="390" '
                         'height="844"></iframe>' + script + "</body></html>", encoding="utf-8")
            res = render.run_chrome(["--allow-file-access-from-files", "--virtual-time-budget=10000",
                                     "--dump-dom", h.as_uri()])
            r = json.loads(html.unescape(re.search(r'<pre id="result">(.*?)</pre>', res.stdout, re.S).group(1)))
        titles = [p["title"] for p in cart["posts"]]
        self.assertEqual(r["before"], titles + ["rest day"])
        self.assertEqual(r["swapped"][:2], [titles[1], titles[0]])
        self.assertEqual(r["done"], [False, True, False, False, False, False, False])
        self.assertEqual(r["sheetDone"], 1)
        self.assertTrue(r["manual"].endswith("done"))
        self.assertEqual(sorted(r["shuffled"]), sorted(r["before"]))
        self.assertEqual(r["shuffled"][6], "rest day")  # rest days stay put

    def test_print_is_one_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            for path in SAMPLES:
                for motif in render.MOTIFS:
                    with self.subTest(cart=path.stem, motif=motif):
                        cart = json.loads(path.read_text(encoding="utf-8"))
                        page = Path(tmp) / f"{path.stem}-{motif}.html"
                        page.write_text(render.render_page(cart, cartridge.layout_week(cart, MONDAY),
                                                           render.load_style(), motif), encoding="utf-8")
                        pdf = Path(tmp) / f"{path.stem}-{motif}.pdf"
                        render.run_chrome(["--virtual-time-budget=6000", "--no-pdf-header-footer",
                                           f"--print-to-pdf={pdf}", page.as_uri()])
                        self.assertTrue(pdf.exists())
                        pages = len(re.findall(rb"/Type\s*/Page[^s]", pdf.read_bytes()))
                        self.assertEqual(pages, 1)


if __name__ == "__main__":
    unittest.main()
