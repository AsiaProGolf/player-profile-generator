# player-profile-generator

Turn a structured JSON player record into a polished golf player profile — a self-contained HTML page and a Markdown variant — with zero dependencies.

Built as part of a two-skill pipeline for golf media and managed-athlete pages:
1. **sports-data-pipeline** gathers the per-player record (field data, rankings, bio).
2. **player-profile-generator (this tool)** renders that record into a profile.

---

## What it produces

Given a JSON record for a player, the renderer outputs:

- **HTML** — a self-contained, light-theme profile card with inlined CSS. Renders directly in a browser with no build step. Two brand skins available (`36media` sky-blue/navy and `tgh` Thai red/navy), both light-background.
- **Markdown** — a portable variant for documentation, a CMS, or sharing as plain text.

Sections rendered (any section whose data is absent is omitted automatically):

1. Header — photo or initials placeholder, name, nickname, nationality flag, Pro/Amateur badge, field-confidence badge.
2. Season snapshot — optional statistics tiles.
3. Rankings — one labeled chip per ranking (OWGR, ADT Order of Merit, Asian Tour Order of Merit, WAGR), each with its own "as of" date. Rankings are never conflated.
4. Bio — born, turned pro, college, hometown, tours played.
5. Career — win count and notable wins list.
6. Recent form — this-season prose and a current-event callout.
7. Fun facts — human-interest lines.
8. Provenance footer — field-confidence status, source, and a reminder to re-pull rankings on event week.

---

## Requirements

Python 3.8+. HTML, Markdown, and Astro generation use no third-party packages — standard library only (`argparse`, `html`, `json`, `os`, `re`, `datetime`).

---

## Usage

```bash
python3 reference/render_profile.py --input PLAYER.json
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--input` | required | JSON file: a single player object or an array of players |
| `--out-dir` | `.` | Directory to write output files |
| `--brand` | `36media` | Brand skin: `36media` or `tgh` |
| `--format` | `both` | Output format: `html`, `md`, or `both` |
| `--embed-fonts` | off | Embed vendored Inter fonts for offline HTML/PDF/PNG |
| `--emit-astro PATH` | none | Generate the Astro component; no input record required |

Output filenames are slugged from `full_name` (e.g. `sample-player.html`). When `--input` is an array, one file is written per player.

---

## Input schema

All fields are optional except `full_name`. The renderer omits any section whose data is absent.

### Core fields

| Field | Type | Notes |
|---|---|---|
| `full_name` | string | **Required.** |
| `also_known_as` | string | Nickname or alternate romanization — shown beside the name. |
| `nationality` | 3-letter code | e.g. `THA`, `JPN`, `USA` → flag emoji + country label. |
| `status` | `Pro` or `Am` | Drives the Pro/Amateur badge. |
| `owgr_rank`, `owgr_best`, `owgr_as_of` | int, int, date | OWGR position, best ever, and the date it was read. |
| `adt_oom_pos`, `adt_oom_as_of` | int, date | Asian Development Tour Order of Merit position + as-of date. |
| `asian_tour_oom_pos`, `asian_tour_oom_as_of` | int, date | Asian Tour Order of Merit position + as-of date. |
| `wagr_rank`, `wagr_as_of` | int, date | World Amateur Golf Ranking (amateurs only) + as-of date. |
| `birth_date` or `birth_year` | date or int | DOB (ISO 8601) or birth year. |
| `age` | int | Current age. |
| `turned_pro_year` | int | Year turned professional. |
| `notable_wins` | array | Each item: `{ "title": ..., "tour": ..., "year": ..., "note": ... }` or a plain string. |
| `recent_form` | string | This-season results, prose. |
| `in_field_confidence` | enum | `confirmed-official`, `confirmed-press`, `notes-only`, or `unconfirmed`. |
| `field_source` | string | What confirmed the field entry — shown in the provenance footer. |

### Profile-enrichment fields

| Field | Type | Notes |
|---|---|---|
| `hometown` | string | e.g. `"Example City"` |
| `college` | string | e.g. `"Example University"` |
| `plays` | array of strings | Tours played, e.g. `["Asian Tour", "All Thailand Golf Tour"]` |
| `pro_wins_count` | int | Total professional wins headline. |
| `this_event` | `{ "name": ..., "summary": ... }` | A highlighted current-event callout under Recent form. |
| `fun_facts` | array of strings | Human-interest lines. |
| `photo_url` | string | Header photo URL; omit or set `null` for an initials placeholder. |

See [`examples/sample-player.json`](examples/sample-player.json) for a complete synthetic record.

---

## Quick start

The included example contains synthetic data only. Run it to regenerate the sample output:

```bash
python3 reference/render_profile.py \
    --input examples/sample-player.json \
    --out-dir examples \
    --format both
```

This writes `examples/sample-player.html` and `examples/sample-player.md`.

---

## Files

```
reference/
  render_profile.py   — renderer: JSON → HTML + Markdown (no dependencies)
  template.html       — annotated HTML skeleton for hand-porting into a CMS or framework
examples/
  sample-player.json   — complete sample input record
  sample-player.html   — rendered HTML output
  sample-player.md     — rendered Markdown output
```

---

## Image export and Astro

Render with `--embed-fonts`, then export a PNG with WeasyPrint, Poppler, and Pillow installed:

```bash
python3 reference/render_profile.py --input examples/sample-player.json --out-dir out --embed-fonts
python3 reference/render_png.py out/sample-player.html --out out/sample-player.png
python3 reference/render_profile.py --emit-astro web/PlayerProfile.astro
```

The generated Astro component shares the renderer's CSS and structure. See [web/README.md](web/README.md) for usage and [SKILL.md](SKILL.md) for the full input schema, tour accents, and licensed-photo requirements. Inter fonts are distributed under the [SIL Open Font License](reference/fonts/OFL.txt).

## Tests

With pytest installed, run `python3 -m pytest -q` from the repository root.

## Extending

- **New nationality:** add an entry to the `FLAGS` dict in `render_profile.py`.
- **New brand skin:** add an entry to the `THEMES` dict; keep the background light.
- **CMS / framework port:** use `reference/template.html` as the markup map — it shows every section and CSS class with data-slot annotations.
- **Batch rendering:** pass a JSON array as `--input`; one output file is written per player.

---

## License

MIT — see [LICENSE](LICENSE).
