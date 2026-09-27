---
name: "player-profile-generator"
description: "Use to turn a structured player record into a polished golf player profile — a web profile page or profile card — for golf media (36Media / Thai Golf Highlights, asiaprogolf.com) and managed athletes, or any tournament player. Pairs with the sports-data-pipeline skill: that gathers the data, this renders it to a clean light-theme HTML profile and a Markdown variant. Keeps every ranking (OWGR / tour Order-of-Merit / WAGR) labeled with its own \"as of\" date and never conflated. Triggers on player profile, athlete profile, profile page, player bio, generate profile, golfer profile, profile card."
---

# Player Profile Generator

Turns a structured per-player record into a polished, on-brand **player profile** — a web profile page or a compact card. Built for 36Media / Thai Golf Highlights coverage (asiaprogolf.com) and managed-athlete pages, but works for any tournament player.

This is the render half of a two-skill pair:

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
| `birth_date` \| `birth_year`, `age`, `turned_pro_year` | date/int | Bio basics. **Age-only** (age but no DOB/year) renders an "Age 23" line — never "Born: age 23". |
| `notable_wins` | array | Each item `{ title, tour, year, note, signature? }` (or a plain string). `signature: true` highlights that win (tinted row + ★). |
| `recent_form` | string | This season's results, prose. |
| `in_field_confidence` | enum | `confirmed-official` \| `confirmed-press` \| `notes-only` \| `unconfirmed` → confidence badge. |
| `field_source` | string | What confirmed the entry — shown in the provenance footer. |

**Profile-enrichment fields (collected in the pipeline's profile pass; optional):**

| Field | Type | Notes |
|---|---|---|
| `hometown` | string | e.g. "Example City". |
| `college` | string | e.g. "Example University". |
| `plays` | array | Tours played, e.g. `["Asian Tour", "All Thailand Golf Tour"]`. |
| `pro_wins_count` | int | Total professional wins headline. |
| `this_event` | `{ name, summary, result? }` | A highlighted current-event callout under Recent form. `result` is an optional bold line (e.g. "R1: 66 (−6) · T3"). |
| `notable_results` | array | Best finishes: each `{ finish, title, tour, year }` (or a string). Renders as finish-chip rows; top-3 finishes are highlighted. |
| `season_stats` | array | Season snapshot tiles: each `{ label, value, sub? }` (e.g. scoring avg, OoM rank, top-10s, earnings). Omitted if absent. |
| `fun_facts` | array of strings | A couple of human-interest lines. |
| `primary_tour` | string | The featured tour that drives the accent theming + header pill. Defaults to `plays[0]` if omitted. |
| `photo_url` | string | Header photo — a **local path or URL to a licensed/credited image**. Falls back to an intentional tour-coloured monogram tile if null. Photo sourcing is an **editorial input**: do NOT scrape or hotlink web photos (licensing). |
| `photo_credit` | string | Optional caption/attribution shown under the photo. |
| `adt_oom_as_of`, `asian_tour_oom_as_of` | date | Optional per-OoM "as of" dates (so every ranking is independently dated). |

See `examples/sample-player.json` for a complete synthetic record.

## The cardinal rule — rankings are never conflated

OWGR, ADT Order of Merit, Asian Tour Order of Merit, and WAGR are **different rankings on different populations.** Each renders as its **own chip with its own "as of" date** — never merged into a single "rank" number. The renderer enforces this; do not pre-flatten them in the input. (This mirrors the sports-data-pipeline discipline: "NEVER merge OWGR and tour-OoM into one number.")

## Profile structure (sections)

1. **Header** — photo (or an intentional tour-coloured monogram tile) + optional credit, full name, nickname, nationality (flag + label), Pro/Amateur badge, **featured-tour pill**, field-confidence badge.
2. **Season snapshot** (optional) — glance-stat tiles from `season_stats` (scoring avg, OoM rank, top-10s, earnings…). Omitted if absent.
3. **Rankings** — one chip per ranking present, each labeled and dated. Never conflated.
4. **Bio** — born (DOB · age) or age-only · turned pro · college · hometown · plays (tours).
5. **Career** — pro-win count pill + notable wins as rich rows (year chip · title · tour tag · note; signature win highlighted).
6. **Recent form** — best-finish result chips + this-season prose + a highlighted "this event" callout.
7. **Fun facts** — a couple of human-interest lines.
8. **Provenance footer** — field-confidence + source + the "re-pull rankings on event week" reminder.

## Render path

```bash
python3 reference/render_profile.py --input PLAYER.json \
    [--out-dir OUT] [--brand 36media|tgh] [--format html|md|both] [--embed-fonts]
```

- `--input` accepts a **single player object OR an array** (renders one slugged file per player — feed it a whole field).
- `--format` → `html`, `md`, or `both` (default both). HTML = the profile page/card; Markdown = a portable variant for docs, CMS, or plain-text sharing.
- `--brand` → the light-theme base skin (below). Default `36media`.
- `--embed-fonts` → inline `@font-face` with the vendored Inter TTFs as data URIs (`reference/fonts/`). Use this for a faithful **offline PDF/PNG render** — without it WeasyPrint falls back to a generic sans. Browser HTML always loads Inter from Google Fonts regardless.
- Output filenames are slugged from `full_name` (e.g. `sample-player.html`).
- Pure Python 3 stdlib — no dependencies. The card CSS lives in `CARD_CSS` (single source of truth; shared with the Astro port).

### Theming — brand base + per-tour accent (all LIGHT)

A **brand base** sets font + navy heading ink + structure; when the brand opts in (`36media`), the player's **primary tour** overlays the accent colour (`--accent` / `--accent-strong` / `--tint`) so the accent bar, ranking chips, win badges and highlights carry the tour's hue — a field of profiles reads as one family while each player carries their tour's colour. Headings stay navy for brand consistency.

| `--brand` | Use for | Tour theming |
|---|---|---|
| `36media` (default) | asiaprogolf.com / 36Media web profiles (Inter, navy) | **On** — per-tour accents |
| `tgh` | Thai Golf Highlights-branded cards | **Off** — fixed TGH red/navy |

Per-tour accents (light, harmonised) live in `TOUR_ACCENTS` in `render_profile.py`: Asian Tour (gold), Asian Development Tour (green), China Tour (red), All Thailand Golf Tour (teal), PGA Tour Americas (blue-navy), DP World Tour, Japan Golf Tour, Korn Ferry, LPGA/LET, plus a sky-blue default. Add a tour by adding an entry + an alias in `TOUR_ALIASES`; keep it light. Everything stays light background / dark text — start light, never dark.

### To export a profile image

Render the HTML with `--embed-fonts`, then run the PNG helper (HTML → WeasyPrint PDF → pdftoppm PNG, auto-cropped to the card):

```bash
python3 reference/render_profile.py --input PLAYER.json --out-dir out/ --embed-fonts
python3 reference/render_png.py out/player.html --out out/player.png --dpi 200
```

Requires `weasyprint` + `pdftoppm` (poppler) + Pillow. For a durable web page, use the Astro component instead.

### Astro component (web port)

`web/PlayerProfile.astro` renders the same profile from a props/JSON contract for asiaprogolf.com (Astro). It is **generated** from the canonical renderer so it cannot fork the design (its `<style>` is `CARD_CSS` verbatim; the theme is injected as inline CSS vars):

```bash
python3 reference/render_profile.py --emit-astro web/PlayerProfile.astro
```

Do not hand-edit it — edit `render_profile.py` (CARD_CSS / structure), then regenerate. Usage + props: `web/README.md`. Verified with `astro build` (Astro 4.x). The standalone HTML remains the canonical design source.

## Example

The example uses synthetic data throughout. `examples/sample-player.json` → rendered `examples/sample-player.html` + `examples/sample-player.md`. Regenerate with:

```bash
python3 reference/render_profile.py --input examples/sample-player.json --out-dir examples
```

## Files

- `reference/render_profile.py` — the renderer (JSON → HTML + Markdown) + `--emit-astro`. Stdlib-only.
- `reference/render_png.py` — HTML → PDF (WeasyPrint) → PNG (pdftoppm), auto-cropped. Needs weasyprint + poppler + Pillow.
- `reference/fonts/Inter-{400,500,600,700,800}.ttf` — vendored Inter for faithful offline rendering (`--embed-fonts`), under the SIL Open Font License 1.1 (`reference/fonts/OFL.txt`).
- `reference/template.html` — annotated HTML structure skeleton (markup map; CARD_CSS is the design source of truth).
- `web/PlayerProfile.astro` — generated Astro component for asiaprogolf.com. `web/README.md` — usage + how to regenerate.
- `examples/sample-player.{json,html,md}` — a complete input record + rendered outputs.

## Notes / extending

- **v2 (publish-grade refinement):** age-only records show an "Age" line (no "Born: age 23"); photo slot accepts a licensed image + credit and otherwise renders an intentional tour-coloured monogram tile; richer Career/Results/Season-snapshot layout (win badges, best finishes, glance stats); per-tour accent theming; an Astro component port; Inter vendored for faithful renders.
- **Amateurs:** set `status: "Am"` and provide `wagr_rank` + `wagr_as_of`; the WAGR chip appears alongside OWGR (amateurs carry both).
- **Missing photo:** leave `photo_url` null → the tour-coloured monogram tile renders (an intentional placeholder, not a debug artifact).
- **Photo sourcing is editorial:** provide a **licensed** local path/URL in `photo_url` (+ `photo_credit`). Never scrape or hotlink web photos.
- **New nationality flag/label:** add the code to the `FLAGS` map in `render_profile.py` (unknown codes fall back to the raw code).
- **New tour accent:** add an entry to `TOUR_ACCENTS` + an alias in `TOUR_ALIASES` — keep it light. **New brand base:** add to `THEMES` (set `tour_theming`).
