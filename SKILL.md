---
name: player-profile-generator
description: Use to turn a structured player record into a polished golf player profile — a web profile page or profile card — for golf media (36Media / Thai Golf Highlights, asiaprogolf.com) and managed athletes, or any tournament player. Pairs with the sports-data-pipeline skill: that gathers the data, this renders it to a clean light-theme HTML profile and a Markdown variant. Keeps every ranking (OWGR / tour Order-of-Merit / WAGR) labeled with its own "as of" date and never conflated. Triggers on player profile, athlete profile, profile page, player bio, generate profile, golfer profile, profile card.
---

# Player Profile Generator

Turns a structured per-player record into a polished, on-brand **player profile** — a web profile page or a compact card. Built for 36Media / Thai Golf Highlights coverage (asiaprogolf.com) and managed-athlete pages, but works for any tournament player.

**This is v1 from a real dogfooding run (ADT Bangkok Classic 2026).** It is the render half of a two-skill pair:

- **sports-data-pipeline** gathers the data (field, rankings, profiles) and emits the per-player record.
- **player-profile-generator (this skill)** renders that record into HTML + Markdown.

If you don't yet have the record, run sports-data-pipeline first. This skill assumes the data exists and is correct.

## When to use

- "Generate a profile page / card for {player}."
- Building an athlete page for asiaprogolf.com or a managed athlete.
- Turning a tournament field's pipeline output into one profile per player.
- Any "player profile / golfer profile / player bio / profile card" request.

## Input — the per-player record

The input is the **flat per-player record emitted by sports-data-pipeline** (its §5 output schema), so a pipeline record passes straight in with no transform. All fields are optional except `full_name`; the renderer omits any section whose data is absent.

**Core fields (from sports-data-pipeline):**

| Field | Type | Notes |
|---|---|---|
| `full_name` | string | Required. |
| `also_known_as` | string | Nickname or alternate romanization — shown beside the name. |
| `nationality` | 3-letter code | e.g. `THA`, `CHN`, `ENG` → flag emoji + country label. |
| `status` | `Pro` \| `Am` | Drives the Pro/Amateur badge. |
| `owgr_rank`, `owgr_best`, `owgr_as_of` | int, int, date | OWGR position + best + the date it was read. |
| `adt_oom_pos`, `asian_tour_oom_pos` | int | Order-of-Merit positions (tour standings). |
| `wagr_rank`, `wagr_as_of` | int, date | Amateurs only — World Amateur Golf Ranking. |
| `birth_date` \| `birth_year`, `age`, `turned_pro_year` | date/int | Bio basics. |
| `notable_wins` | array | Each item `{ title, tour, year, note }` (or a plain string). |
| `recent_form` | string | This season's results, prose. |
| `in_field_confidence` | enum | `confirmed-official` \| `confirmed-press` \| `notes-only` \| `unconfirmed` → confidence badge. |
| `field_source` | string | What confirmed the entry — shown in the provenance footer. |

**Profile-enrichment fields (collected in the pipeline's profile pass; optional):**

| Field | Type | Notes |
|---|---|---|
| `hometown` | string | e.g. "Nonthaburi, Thailand". |
| `college` | string | e.g. "Virginia Tech". |
| `plays` | array | Tours played, e.g. `["Asian Tour", "All Thailand Golf Tour"]`. |
| `pro_wins_count` | int | Total professional wins headline. |
| `this_event` | `{ name, summary }` | A highlighted current-event callout under Recent form. |
| `fun_facts` | array of strings | A couple of human-interest lines. |
| `photo_url` | string | Header photo; falls back to an initials placeholder if null. |
| `adt_oom_as_of`, `asian_tour_oom_as_of` | date | Optional per-OoM "as of" dates (v1 extension so every ranking is independently dated). |

See `examples/sarit-suwannarut.json` for a complete record.

## The cardinal rule — rankings are never conflated

OWGR, ADT Order of Merit, Asian Tour Order of Merit, and WAGR are **different rankings on different populations.** Each renders as its **own chip with its own "as of" date** — never merged into a single "rank" number. The renderer enforces this; do not pre-flatten them in the input. (This mirrors the sports-data-pipeline discipline: "NEVER merge OWGR and tour-OoM into one number.")

## Profile structure (sections)

1. **Header** — photo slot (or initials placeholder), full name, nickname, nationality (flag + label), Pro/Amateur badge, field-confidence badge.
2. **Rankings** — one chip per ranking present, each labeled and dated. Never conflated.
3. **Bio** — born (DOB/age) · turned pro · college · hometown · plays (tours).
4. **Career** — pro-win count + notable wins (year — title (tour, note)).
5. **Recent form** — this-season prose + a highlighted "this event" callout.
6. **Fun facts** — a couple of human-interest lines.
7. **Provenance footer** — field-confidence + source + the "re-pull rankings on event week" reminder.

## Render path

```bash
python3 reference/render_profile.py --input PLAYER.json \
    [--out-dir OUT] [--brand 36media|tgh] [--format html|md|both]
```

- `--input` accepts a **single player object OR an array** (renders one slugged file per player — feed it a whole field).
- `--format` → `html`, `md`, or `both` (default both). HTML = the profile page/card; Markdown = a portable variant for docs, CMS, or Telegram.
- `--brand` → the light-theme skin (below). Default `36media`.
- Output filenames are slugged from `full_name` (e.g. `sarit-suwannarut.html`).
- Pure Python 3 stdlib — no dependencies. The HTML is self-contained (inlined CSS).

### Brand skins — both LIGHT

| `--brand` | Use for | Type | Accent palette |
|---|---|---|---|
| `36media` (default) | asiaprogolf.com / 36Media web profiles | Inter | sky blue `#7AC8FF` + navy `#25477A` on white |
| `tgh` | Thai Golf Highlights-branded cards | system sans | Thai red `#C8102E` + deep navy `#1B2563` on white |

Both default to a light background with dark text — start light, never dark. Brand colors live in the `THEMES` dict in `render_profile.py`; edit there (or add a new entry) rather than reinventing colors inline, and keep any new skin light.

### To export a profile image

The HTML targets a browser. For a glance-and-decide image (e.g. to share on a chat app), screenshot the rendered HTML with a headless browser, or convert it via an HTML→PDF→PNG pipeline. For a durable page, use the HTML directly.

## Example

`examples/sarit-suwannarut.json` → rendered `examples/sarit-suwannarut.html` + `examples/sarit-suwannarut.md` (Sarit Suwannarut, the Bangkok Classic 2026 R1 leader, from the dogfooding run). Regenerate with:

```bash
python3 reference/render_profile.py --input examples/sarit-suwannarut.json --out-dir examples
```

## Files

- `reference/render_profile.py` — the renderer (JSON → HTML + Markdown). Dependency-free.
- `reference/template.html` — annotated HTML structure skeleton for hand-porting into Astro / WordPress / a CMS.
- `examples/sarit-suwannarut.json` — a complete input record.
- `examples/sarit-suwannarut.{html,md}` — the rendered outputs.

## v1 notes / extending

- **Amateurs:** set `status: "Am"` and provide `wagr_rank` + `wagr_as_of`; the WAGR chip appears alongside OWGR (amateurs carry both).
- **Missing photo:** leave `photo_url` null → a clean initials placeholder renders.
- **New nationality flag/label:** add the code to the `FLAGS` map in `render_profile.py` (unknown codes fall back to showing the raw code).
- **New brand skin:** add an entry to the `THEMES` dict — keep it light.
- Likely next steps: an Astro/WordPress component port (using `template.html`), a compact "field grid" layout (many cards on one page), and a built-in headless-screenshot step for image delivery.
