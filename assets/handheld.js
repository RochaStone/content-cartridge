/* content-cartridge page script. Python renders every fragment; this only moves them between days,
   remembers what is done, and writes week.ics and week.md from the current week.
   week.ics and week.md here mirror cartridge.py exactly; tests/test_cartridge.py checks they match. */
(function () {
  "use strict";
  var DATA = JSON.parse(document.getElementById("cart-data").textContent);
  var DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  var DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var KEY = "content-cartridge:" + DATA.slug + ":" + DATA.start;
  var state = { slots: DATA.slots.slice(), done: [false, false, false, false, false, false, false],
                sel: 0, held: null, started: false };
  var selftest = /selftest/.test(location.hash);
  var autoplay = selftest || /play/.test(location.hash);

  function $(s, root) { return (root || document).querySelector(s); }
  function $$(s, root) { return Array.prototype.slice.call((root || document).querySelectorAll(s)); }

  function load() {
    if (selftest) return;
    try {
      var saved = JSON.parse(window.localStorage.getItem(KEY) || "null");
      if (saved && saved.slots && saved.slots.length === 7 && saved.done && saved.done.length === 7) {
        state.slots = saved.slots; state.done = saved.done;
      }
    } catch (err) { state.note = "This browser is not keeping notes, so done marks reset on reload."; }
  }
  function save() {
    if (selftest) return;
    try { window.localStorage.setItem(KEY, JSON.stringify({ slots: state.slots, done: state.done })); }
    catch (err) { state.note = "This browser is not keeping notes, so done marks reset on reload."; }
  }

  function dateOf(i) {
    var p = DATA.start.split("-");
    return new Date(Date.UTC(+p[0], +p[1] - 1, +p[2] + i));
  }
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function ymd(d) { return d.getUTCFullYear() + pad(d.getUTCMonth() + 1) + pad(d.getUTCDate()); }
  function iso(d) { return d.getUTCFullYear() + "-" + pad(d.getUTCMonth() + 1) + "-" + pad(d.getUTCDate()); }

  function tpl(kind, post) {
    var t = document.getElementById("t-" + kind + "-" + (post === null ? "rest" : post));
    return t ? t.innerHTML : "";
  }

  function paint() {
    $$(".row").forEach(function (row) {
      var i = +row.getAttribute("data-day");
      $(".slot", row).innerHTML = tpl("row", state.slots[i]);
      row.classList.toggle("sel", i === state.sel);
      row.classList.toggle("done", state.done[i]);
      row.classList.toggle("held", i === state.held);
    });
    $$(".s-row").forEach(function (row) {
      var i = +row.getAttribute("data-day");
      $(".s-slot", row).innerHTML = tpl("sheet", state.slots[i]);
      row.classList.toggle("done", state.done[i]);
      var box = $(".box", row);
      if (box) box.setAttribute("aria-pressed", state.done[i] ? "true" : "false");
    });
    var det = $("#m-detail");
    if (det) {
      var d = dateOf(state.sel);
      det.innerHTML = tpl("man", state.slots[state.sel]);
      $("#m-day").textContent = DAYS[state.sel] + " " + pad(d.getUTCDate()) + " " + MONTHS[d.getUTCMonth()] +
        (state.done[state.sel] ? " · done" : "");
    }
  }
  function say(msg) { var s = $(".status"); if (s) s.textContent = msg; }

  function start() {
    state.started = true;
    var boot = $(".boot"), wk = $(".weekview");
    if (boot) boot.hidden = true;
    if (wk) wk.hidden = false;
    paint();
    say(state.note || "A done · B swap · SEL shuffle");
  }

  function shuffle() {
    var idx = [], posts = [];
    state.slots.forEach(function (p, i) { if (p !== null) { idx.push(i); posts.push(p); } });
    for (var i = posts.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1)), t = posts[i]; posts[i] = posts[j]; posts[j] = t;
    }
    idx.forEach(function (d, k) { state.slots[d] = posts[k]; });
    state.done = state.done.map(function () { return false; });
    state.held = null;
    save(); paint(); say("shuffled. rest days stay put");
  }

  function swap() {
    if (state.held === null) { state.held = state.sel; paint(); say("move, then B again to swap"); return; }
    var a = state.held, b = state.sel;
    var t = state.slots[a]; state.slots[a] = state.slots[b]; state.slots[b] = t;
    var u = state.done[a]; state.done[a] = state.done[b]; state.done[b] = u;
    state.held = null;
    save(); paint(); say(a === b ? "swap cancelled" : DAYS[a] + " and " + DAYS[b] + " swapped");
  }

  function toggleDone(i) {
    state.done[i] = !state.done[i];
    save(); paint();
    var left = state.slots.filter(function (p, k) { return p !== null && !state.done[k]; }).length;
    say(left ? left + " to go" : "week done. well played");
  }

  /* ---------- week.ics and week.md (mirrors cartridge.py) ---------- */
  function icsEscape(s) {
    return String(s).replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,")
      .replace(/\r\n/g, "\\n").replace(/\n/g, "\\n");
  }
  function icsFold(line) {
    var enc = new TextEncoder(), out = [], cur = "", len = 0;
    Array.from(line).forEach(function (ch) {
      var b = enc.encode(ch).length;
      if (len + b > (out.length ? 74 : 75)) { out.push(cur); cur = ""; len = 0; }
      cur += ch; len += b;
    });
    out.push(cur);
    return out.join("\r\n ");
  }
  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
  function description(post) {
    var lines = ["Hook: " + post.hook, ""].concat(post.beats.map(function (b) { return "- " + b; }));
    return lines.concat(["", "CTA: " + DATA.cta, "Pillar: " + DATA.name]).join("\n");
  }
  function buildIcs(stamp) {
    var rows = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Rocha Coded//content-cartridge//EN",
      "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:" + icsEscape(DATA.name)];
    state.slots.forEach(function (p, i) {
      if (p === null) return;
      var post = DATA.posts[p], d = dateOf(i), next = dateOf(i + 1);
      rows.push("BEGIN:VEVENT", "UID:" + DATA.slug + "-" + ymd(d) + "-" + p + "@content-cartridge",
        "DTSTAMP:" + stamp, "DTSTART;VALUE=DATE:" + ymd(d), "DTEND;VALUE=DATE:" + ymd(next),
        "SUMMARY:" + icsEscape("[" + cap(post.format) + "] " + post.title),
        "DESCRIPTION:" + icsEscape(description(post)), "CATEGORIES:" + icsEscape(DATA.name),
        "TRANSP:TRANSPARENT", "END:VEVENT");
    });
    rows.push("END:VCALENDAR");
    return rows.map(icsFold).join("\r\n") + "\r\n";
  }
  function buildMd() {
    var out = ["# " + DATA.name + ": the week of " + iso(dateOf(0)), "", "For: " + DATA.audience,
      "Promise: " + DATA.promise, "CTA: " + DATA.cta, ""];
    state.slots.forEach(function (p, i) {
      var d = dateOf(i), head = "## " + DAY_NAMES[i] + " " + d.getUTCDate() + " " + MONTHS[d.getUTCMonth()];
      if (p === null) { out.push(head, "", "Rest day. Reply to comments, save ideas, live your life.", ""); return; }
      var post = DATA.posts[p];
      out.push(head + ": " + post.title + " (" + post.format + ")", "", "**Hook:** " + post.hook, "");
      post.beats.forEach(function (b) { out.push("- " + b); });
      out.push("");
    });
    out.push("## Reel shot list", "");
    DATA.shot_list.forEach(function (s, i) { out.push((i + 1) + ". " + s.shot + (s.note ? " (" + s.note + ")" : "")); });
    out.push("", "Week ends " + iso(dateOf(6)) + ". Made with content-cartridge.", "");
    return out.join("\n");
  }
  function utcStamp() {
    var n = new Date();
    return n.getUTCFullYear() + pad(n.getUTCMonth() + 1) + pad(n.getUTCDate()) + "T" +
      pad(n.getUTCHours()) + pad(n.getUTCMinutes()) + pad(n.getUTCSeconds()) + "Z";
  }
  function download(name, text, type) {
    var url = URL.createObjectURL(new Blob([text], { type: type }));
    var a = document.createElement("a");
    a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
  }
  function saveFiles() {
    download("week.ics", buildIcs(utcStamp()), "text/calendar");
    setTimeout(function () { download("week.md", buildMd(), "text/markdown"); }, 400);
    say("saved week.ics + week.md");
  }

  /* ---------- buttons and keys ---------- */
  function press(k, day) {
    if (k === "print") { window.print(); return; }
    if (k === "save") { saveFiles(); return; }
    if (k === "done") { toggleDone(+day); return; }
    if (k === "select" && !document.querySelector(".handheld")) { shuffle(); return; }
    if (!state.started) { if (k === "start" || k === "a") start(); return; }
    if (k === "up" || k === "left") { state.sel = (state.sel + 6) % 7; paint(); }
    else if (k === "down" || k === "right") { state.sel = (state.sel + 1) % 7; paint(); }
    else if (k === "a") toggleDone(state.sel);
    else if (k === "b") swap();
    else if (k === "select") shuffle();
    else if (k === "start") { state.sel = 0; state.held = null; paint(); say("back to monday"); }
  }
  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-k]");
    if (btn) press(btn.getAttribute("data-k"), btn.getAttribute("data-day"));
    var row = ev.target.closest(".row");
    if (row && state.started) { state.sel = +row.getAttribute("data-day"); paint(); }
  });
  var KEYS = { ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right", Enter: "start",
               a: "a", x: "a", b: "b", z: "b", Shift: "select", s: "save", p: "print" };
  document.addEventListener("keydown", function (ev) {
    if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
    var k = KEYS[ev.key] || KEYS[(ev.key || "").toLowerCase()];
    if (!k || !document.querySelector(".handheld")) return;
    if (/^Arrow/.test(ev.key)) ev.preventDefault();
    press(k);
  });

  load();
  paint();
  if (selftest || /still/.test(location.hash)) document.body.classList.add("still");
  if (autoplay) start();
  if (selftest) {
    var out = document.createElement("div");
    out.id = "selftest"; out.hidden = true;
    out.setAttribute("data-ics", buildIcs("20260101T000000Z"));
    out.setAttribute("data-md", buildMd());
    document.body.appendChild(out);
  }
})();
