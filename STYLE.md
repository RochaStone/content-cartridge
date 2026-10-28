# style.json

One file holds your look. Every Rocha Coded tool reads the same file, so you make it once.

## Where it goes
The tool looks in this order and uses the first one it finds:
1. `style.json` in the folder you are working in (your Cowork folder, or wherever you run Claude Code), or a file you name with `--style`
2. `~/.rocha-coded/style.json`, to use one look across every project
3. `examples/style.rocha-coded.json`, the bundled example (Rocha's look)

Start from `style.example.json`: copy it to `style.json` and fill it in. Or ask Claude to make one with you.

## The keys
| Key | What to put there | Used by this tool |
|---|---|---|
| `name` | your brand or studio name | yes, the logo under the screen (blank prints "content cartridge") |
| `owner` | your name, as you sign things | yes, at the foot of the printed sheet |
| `handle` | your Instagram or main social handle, with the @ | yes, next to your name |
| `site` | your website address | no |
| `palette.hero` | your ground colour, the deep one everything sits on, as a hex code like `#50163C` | the page behind the handheld and the booklet (never a fill) |
| `palette.plum` | a deep shade | the handheld shell |
| `palette.wine` | a second deep colour | the cartridge, headlines, day labels |
| `palette.accent` | your one bright accent | the A button, format chips, pills |
| `palette.paper` | a light paper colour | the screen, the manual card, the printed sheet |
| `palette.paper_pink` | a second paper colour | the cartridge label and the CTA box |
| `palette.ink` | your text colour | text, the screen bezel, the D-pad |
| `palette.marker` | the colour of the handwritten scrawl | the scrawl and the stamp |
| `palette.gold` | a highlight colour for thin rules | screws, the B button, rules |
| `palette.cool` | one cool accent, used rarely | no |
| `fonts.masthead` | a big display font from Google Fonts | the pillar name, titles, dates |
| `fonts.label` | a font for labels and small print | labels and buttons |
| `fonts.body` | a reading font | hooks and beats on the manual and sheet |
| `fonts.scrawl` | a handwriting or marker font | the scrawl |
| `fonts.script` | a signature script font | no |
| `fonts.mono` | a typewriter font | dates, beats on the printed sheet |
| `fonts.pixel` (optional) | a pixel font from Google Fonts | the screen and the blog window labels (Silkscreen if empty) |
| `motif` | `cyberpunk` (the handheld), `analog` (the printed booklet) or `y2k-blog` (the handheld in a blog window). Older names like `guest-check` or `retro-tv` still work and map to the nearest one | yes |
| `lines.scrawl` | a short line in your own words | under the pillar name on the cartridge label and the sheet |
| `lines.stamp` | one word for a rubber stamp | on the printed sheet |
| `lines.masthead`, `headline`, `todo`, `celebrate`, `affirm`, `invite`, `magazine` | more of your own lines | kept for other tools |
| `references` | 3 to 5 images or links that feel like you | Claude looks at these when it makes your style with you |
| `notes` | your look in one or two sentences | Claude reads this too |

## Good to know
- Colours must be hex codes (`#RRGGBB`). Anything else is skipped and the bundled colour is used for that slot.
- Fonts are Google Fonts names, letters, numbers and spaces only. If a font is not on Google Fonts, or you are offline, the page uses a similar font already on your computer.
- Any colour or font you leave empty borrows the bundled example's, so the page always looks finished.
- Your words and your name never borrow. Leave `lines.scrawl`, `lines.stamp`, `owner` or `handle` empty and the page prints nothing there.
