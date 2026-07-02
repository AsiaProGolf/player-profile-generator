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
2. Rankings — one labeled chip per ranking (OWGR, ADT Order of Merit, Asian Tour Order of Merit, WAGR), each with its own "as of" date. Rankings are never conflated.
3. Bio — born, turned pro, college, hometown, tours played.
4. Career — win count and notable wins list.
5. Recent form — this-season prose and a current-event callout.
6. Fun facts — human-interest lines.
7. Provenance footer — field-confidence status, source, and a reminder to re-pull rankings on event week.

---

## Requirements

Python 3.8+. No third-party packages — standard library only (`argparse`, `html`, `json`, `os`, `re`, `datetime`).

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

Output filenames are slugged from `full_name` (e.g. `sarit-suwannarut.html`). When `--input` is an array, one file is written per player.

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
| `hometown` | string | e.g. `"Nonthaburi, Thailand"` |
| `college` | string | e.g. `"Virginia Tech"` |
| `plays` | array of strings | Tours played, e.g. `["Asian Tour", "All Thailand Golf Tour"]` |
| `pro_wins_count` | int | Total professional wins headline. |
| `this_event` | `{ "name": ..., "summary": ... }` | A highlighted current-event callout under Recent form. |
| `fun_facts` | array of strings | Human-interest lines. |
| `photo_url` | string | Header photo URL; omit or set `null` for an initials placeholder. |

See [`examples/sarit-suwannarut.json`](examples/sarit-suwannarut.json) for a complete record.

---

## Quick start

Run the included example to regenerate the sample output:

```bash
python3 reference/render_profile.py \
    --input examples/sarit-suwannarut.json \
    --out-dir examples \
    --format both
```

This writes `examples/sarit-suwannarut.html` and `examples/sarit-suwannarut.md`.

---

## Files

```
reference/
  render_profile.py   — renderer: JSON → HTML + Markdown (no dependencies)
  template.html       — annotated HTML skeleton for hand-porting into a CMS or framework
examples/
  sarit-suwannarut.json   — complete sample input record
  sarit-suwannarut.html   — rendered HTML output
  sarit-suwannarut.md     — rendered Markdown output
```

---

## Extending

- **New nationality:** add an entry to the `FLAGS` dict in `render_profile.py`.
- **New brand skin:** add an entry to the `THEMES` dict; keep the background light.
- **CMS / framework port:** use `reference/template.html` as the markup map — it shows every section and CSS class with data-slot annotations.
- **Batch rendering:** pass a JSON array as `--input`; one output file is written per player.

---

## License

MIT — see [LICENSE](LICENSE).
