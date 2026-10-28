# Testing

Everything below was run on 28 Oct 2026, on macOS 26.6 with Python 3.12.8 and Google Chrome 156 installed.

## 1. The tests
```sh
python3 -m unittest discover -s tests -v
```
Result: **28 tests, all OK** (about 100 seconds; the Chrome tests are most of it). They cover:
- **Cartridge schema:** the three samples pass; 4 and 8 posts are refused; a bad slug, an empty CTA, an unknown
  format, empty beats, an overlong hook and a shot with no text are each named in plain words; broken JSON gets a
  kind message; the `check` command exits non-zero and says what to fix.
- **The week, as a pure function:** 7 posts fill Monday to Sunday in her order; 6 posts rest on Sunday; 5 posts
  rest on Wednesday and Sunday; a seed gives the same shuffle every time and keeps every post exactly once; the
  cartridge is not changed; the week must start on a Monday; `next_monday`; a week that crosses into a new year.
- **week.ics validity:** a small RFC 5545 parser written for the tests checks CRLF line endings, lines of 75
  octets or fewer, unfolding, BEGIN/END nesting, one VCALENDAR with VERSION 2.0 and PRODID, one VEVENT per post,
  unique UIDs, DTSTAMP, all-day DTSTART and DTEND one day apart, and that SUMMARY and DESCRIPTION unescape back to
  the original text, including commas, semicolons, backslashes and long accented lines. The parser itself is
  checked to reject a missing END and LF-only line endings.
- **week.md:** title, seven day headings plus the shot list, rest days, a dated heading.
- **Three motifs from one function:** cyberpunk (the handheld, PRESS START, Silkscreen), analog (the cartridge
  insert, no handheld), y2k-blog (`content-cartridge.exe`, hit counter `000,777`, guestbook link to Issues); every
  motif carries the print sheet; no `text-shadow`; no em dash; motif choice from `--motif`, then style.json, then
  cyberpunk, with old names mapped.
- **Safety:** her words are escaped in the page and in the embedded data; bad colours and font names are not
  injected into the CSS.
- **style.json:** the fallback order (`./style.json`, `~/.rocha-coded/style.json`, the bundled example); a user
  style borrows only missing palette and font entries and never the example's lines, owner, handle, name,
  references or notes, so a user file without lines prints no scrawl, no LORE stamp and no handle; both bundled
  style files share the same keys.
- **The command line:** `build` writes the page, a valid `week.ics` with 5 events, and `week.md`, and snaps
  `--start 2026-10-28` to Monday 2 Nov.
- **Headless Chrome, real renders:** each of the 3 cartridges in each of the 3 motifs is loaded in a 390px wide
  frame: page width stays 390 (no sideways scroll), 7 screen rows (none in analog) and 7 sheet rows. In the same
  run the page script builds `week.ics` and `week.md` in the browser, and both are byte-for-byte identical to the
  Python files. A second test presses the real buttons: B, down, B swaps Monday and Tuesday; A marks Tuesday done
  on the screen, the sheet and the manual card; SELECT shuffles and leaves the rest day on Sunday. A third test
  prints all 9 combinations to PDF: each is exactly one page.

Headless Chrome on macOS will not open a window narrower than 500px, so the 390px checks run inside a 390px
iframe. Without Chrome, the three Chrome tests are skipped and say so.

## 2. By eye
`python3 scripts/make-readme-images.py` rendered the three motifs at 1080x1350 and the triptych at 1620x720.
Each was opened and looked at. Fixes made on the way: the cartridge label was hidden behind the shell, the
speaker grille sat over the PRINT button, and the y2k marquee scrolled mid-picture (pictures now use a still mode).
The handheld with PRESS START, the laid-out week, the analog booklet and the y2k window were all checked.

## 3. Security gate
```sh
./scripts/security-check.sh
```
Result: 9 passed, 0 failed, **SAFE TO PUBLISH**.

## Not tested
- SAVE in a real browser with a person clicking: the download files are built by the same code the tests check,
  but the browser's download prompt (and "allow multiple downloads") was not clicked through.
- Opening `week.ics` in Apple Calendar, Google Calendar or Outlook. The file passes the parser above; no calendar
  app import was run.
- The printed page on paper. The PDF is one A4 page; US Letter was not checked.
- Claude Cowork upload of the zip, and the SKILL.md interview end to end with a real person.
- Windows.
