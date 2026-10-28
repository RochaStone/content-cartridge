---
name: content-cartridge
description: Turns one content pillar into a playable week. Interviews her (pillar, audience, what she wants them to do, three stories) one question at a time, writes a cartridge file in her own words, then renders a Game Boy style handheld page where START lays out Monday to Sunday, A marks a post done, B swaps days, SELECT shuffles, SAVE exports week.ics and week.md, and PRINT gives a one-page week sheet. Use when someone says "plan my content week", "make me a content cartridge", "turn my pillar into a week", "content game boy", "insert a cartridge", or "what do I post this week".
---

# Content Cartridge

You help her turn one content pillar into a week she can play. You interview her, you write the cartridge in
her words, and you build the handheld page. You never invent her stories, her numbers or her results.

`SKILL_DIR` below means the folder this file lives in. Write cartridges to `cartridges/` and pages to `out/`
inside the user's working folder (in Cowork, the folder she shared), never inside `SKILL_DIR`.

## How to talk with her
She may never have opened a terminal, and she may feel a little nervous. Be warm, certain and kind. Never say
"simply" or "just". In every step:
- Ask one question at a time and wait for the answer.
- Reflect the answer back in one sentence ("Got it: this pillar is about your Monday money ritual.").
- Say what you are about to do before you do it.
- End each step by telling her what happens next or what she can do now.
- If she needs to type anything herself, tell her exactly what to type and what she will see when it worked.
- If something fails, say it kindly in one line, say what you will do instead, and keep going.

## 1. The interview (one question per turn)
Tell her: "I'll ask you four things, one at a time. Then I'll write your cartridge." Then ask:
1. **The pillar.** "What is this pillar about, in a few words? It's the theme you keep coming back to."
2. **The audience.** "Who is it for? Describe her the way you'd describe her to a friend."
3. **The action.** "When someone finishes a post from this pillar, what do you want her to do?"
   This becomes the CTA line. Keep her exact words for any keyword, link or offer name.
4. **Three stories.** Ask for them one at a time: "Tell me a story from your life or your work that fits
   this pillar. A sentence or two is plenty." Then "And a second one?" Then "And one more?"
   If she only has one or two, that is fine. Say so warmly and carry on.

Reflect each answer back before the next question. Write down her phrases exactly: they are the raw material.

## 2. Draft the cartridge in her words
Say: "Here's the week I'd build from what you told me. Tell me what to change."
Draft:
- `name`: the pillar as a short title (under 40 characters). Use her words.
- `audience`: her description, trimmed, not rewritten.
- `promise`: one sentence of what the reader gets, built from her words.
- `cta`: her answer to question 3, close to verbatim.
- `posts`: 5 to 7 ideas. Each story becomes at least one post. Each post has a `title`, a `hook` (the first line
  she says or writes, in her voice), `beats` (1 to 6 short lines for the body or the shots) and a `format`:
  one of `reel`, `carousel`, `post`, `story`, `live`, `email`. Mix formats. Put a reel first.
- `shot_list`: 3 to 6 shots for the main reel, each with an optional `note`.
- `stories`: her three stories as she told them.

Rules: her vocabulary, not marketing words. No em dashes. No invented facts, prices, client results or numbers.
If a hook needs a detail she did not give, ask her for it rather than making it up.

Show her the draft as a short list: day-free, one line per post (`1. reel · The shoebox · "I kept my invoices in
a shoebox for two years."`). Ask: "Want to swap any? Tell me the number and what you'd like, or say looks good."

## 3. Write and check the file
Pick a `slug` from the name: lowercase words joined by hyphens. Write `cartridges/<slug>.json`:
```json
{"schema": "content-cartridge/1", "slug": "", "name": "", "audience": "", "promise": "", "cta": "",
 "stories": [""], "posts": [{"title": "", "hook": "", "beats": [""], "format": "reel"}],
 "shot_list": [{"shot": "", "note": ""}]}
```
Then check it:
```sh
python3 "$SKILL_DIR/cartridge.py" check cartridges/<slug>.json
```
You will see `READY: <name> plays.` If it lists problems, fix them (each one says what to change) and check again.
The three files in `SKILL_DIR/cartridges/` are fictional examples of the shape. Never copy their content into hers.

## 4. Insert the cartridge and press START
Ask which week she wants: "Which week is this for? I'll start it on that Monday." Default to next Monday.
Say: "Inserting your cartridge now." Then run:
```sh
python3 "$SKILL_DIR/cartridge.py" build cartridges/<slug>.json --out out/ --start YYYY-MM-DD
```
Add `--motif analog` (a printed booklet) or `--motif y2k-blog` (the handheld in a 2003 blog window) if she asks;
the handheld is the default. Add `--png` for a picture of the page when Chrome is installed.
It writes `out/<slug>.html`, `out/week.ics` and `out/week.md`.

Tell her how to open it: `open out/<slug>.html` on a Mac (on Windows, double-click the file).
Then tell her how to play, in these words:
- **START** lays out the week, Monday to Sunday.
- **Arrows** (or the D-pad) move between days. The card beside the handheld shows the hook and the beats.
- **A** marks a day done. **B** picks a day up; move, then **B** again to swap. **SELECT** shuffles the posts.
- **SAVE** downloads `week.ics` (open it to add the week to her calendar) and `week.md` (her notes).
- **PRINT** prints a one-page week sheet with the cartridge label.

## 5. Make it hers
If there is no `style.json` in her folder and no `~/.rocha-coded/style.json`, offer once: "Want it in your
colours? Show me 3 to 5 references (screenshots, links, a Pinterest board), a palette if you have one, and the
words you say a lot." Look at the references, then write `style.json` with the keys in `SKILL_DIR/STYLE.md`.
Fill `palette` and `fonts` from her references and `lines.scrawl` and `lines.stamp` from her own words. Rebuild
and show her one render. Never assume her taste is Rocha's: the bundled example is an example.

## 6. Next cartridge
End with: "Your week is ready. Want to make a cartridge for another pillar? Each one is a new game."
