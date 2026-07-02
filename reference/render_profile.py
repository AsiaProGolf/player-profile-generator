#!/usr/bin/env python3
"""player-profile-generator — render a structured golf player record to HTML + Markdown.

Pairs with the sports-data-pipeline skill: that gathers the per-player record,
this renders it into a polished profile page/card. Input = the flat per-player
schema emitted by sports-data-pipeline (see SKILL.md), plus optional
profile-enrichment fields (college, hometown, plays, this_event, fun_facts,
photo_url) that the pipeline's profile pass collects.

Design: LIGHT theme by default (light background, dark text). Two brand
skins — 36media (Inter, sky-blue/navy; the asiaprogolf.com web brand, default)
and tgh (Thai Golf Highlights navy/red).

Every ranking (OWGR / tour Order-of-Merit / WAGR) renders as its own chip with
its own "as of" date. Rankings are NEVER conflated into one number.

Usage:
    python3 render_profile.py --input player.json
    python3 render_profile.py --input field.json --out-dir out/ --brand 36media --format both

`--input` may be a single player object OR an array of players (renders each to
its own slugged file). `--format` = html | md | both (default both).
"""
import argparse
import html
import json
import os
import re
import sys
from datetime import datetime

# --- Brand skins (both LIGHT) ----------------
THEMES = {
    "36media": {
        "label": "36Media / Asia Pro Golf",
        "font": '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        "font_link": (
            '<link rel="preconnect" href="https://fonts.googleapis.com">'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
        ),
        "paper": "#ffffff",
        "ink": "#25477A",          # dark navy — headings
        "ink2": "#33649E",         # medium blue
        "accent": "#7AC8FF",       # sky blue — bars/fills
        "accent_strong": "#33649E",
        "text": "#1F1F1F",         # near-black body
        "muted": "#6B7280",
        "tan": "#A17C5A",
        "line": "#E5E9F0",
        "tint": "#EEF5FC",
    },
    "tgh": {
        "label": "Thai Golf Highlights",
        "font": '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        "font_link": "",
        "paper": "#ffffff",
        "ink": "#1B2563",          # deep navy
        "ink2": "#1B2563",
        "accent": "#C8102E",       # Thai red
        "accent_strong": "#C8102E",
        "text": "#1F1F1F",
        "muted": "#6B7280",
        "tan": "#A17C5A",
        "line": "#E7E9F2",
        "tint": "#F4F6FC",
    },
}

# nationality code -> (flag emoji, display label). Falls back to the raw code.
FLAGS = {
    "THA": ("\U0001F1F9\U0001F1ED", "Thailand"),
    "CHN": ("\U0001F1E8\U0001F1F3", "China"),
    "HKG": ("\U0001F1ED\U0001F1F0", "Hong Kong"),
    "TPE": ("\U0001F1F9\U0001F1FC", "Chinese Taipei"),
    "IND": ("\U0001F1EE\U0001F1F3", "India"),
    "PHI": ("\U0001F1F5\U0001F1ED", "Philippines"),
    "KOR": ("\U0001F1F0\U0001F1F7", "South Korea"),
    "JPN": ("\U0001F1EF\U0001F1F5", "Japan"),
    "MAS": ("\U0001F1F2\U0001F1FE", "Malaysia"),
    "SGP": ("\U0001F1F8\U0001F1EC", "Singapore"),
    "INA": ("\U0001F1EE\U0001F1E9", "Indonesia"),
    "VIE": ("\U0001F1FB\U0001F1F3", "Vietnam"),
    "USA": ("\U0001F1FA\U0001F1F8", "United States"),
    "MEX": ("\U0001F1F2\U0001F1FD", "Mexico"),
    "CAN": ("\U0001F1E8\U0001F1E6", "Canada"),
    "AUS": ("\U0001F1E6\U0001F1FA", "Australia"),
    "NZL": ("\U0001F1F3\U0001F1FF", "New Zealand"),
    "RSA": ("\U0001F1FF\U0001F1E6", "South Africa"),
    "ENG": ("\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F", "England"),
    "SCO": ("\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F", "Scotland"),
    "WLS": ("\U0001F3F4\U000E0067\U000E0062\U000E0077\U000E006C\U000E0073\U000E007F", "Wales"),
    "NIR": ("\U0001F1EC\U0001F1E7", "Northern Ireland"),
    "IRL": ("\U0001F1EE\U0001F1EA", "Ireland"),
    "ESP": ("\U0001F1EA\U0001F1F8", "Spain"),
    "FRA": ("\U0001F1EB\U0001F1F7", "France"),
    "GER": ("\U0001F1E9\U0001F1EA", "Germany"),
    "SWE": ("\U0001F1F8\U0001F1EA", "Sweden"),
    "ITA": ("\U0001F1EE\U0001F1F9", "Italy"),
}

CONFIDENCE_LABELS = {
    "confirmed-official": "Confirmed (official)",
    "confirmed-press": "Confirmed (press)",
    "notes-only": "Notes only — unverified for this field",
    "unconfirmed": "Field entry UNCONFIRMED",
}


# --- helpers ----------------------------------------------------------------
def e(s):
    """HTML-escape, treating None as empty."""
    return html.escape(str(s)) if s is not None else ""


def fmt_date(s):
    """ISO date/month -> human display. Returns None if absent/unparseable-as-empty."""
    if not s:
        return None
    for fmt, out in (("%Y-%m-%d", "%-d %b %Y"), ("%Y-%m", "%b %Y")):
        try:
            return datetime.strptime(s, fmt).strftime(out)
        except ValueError:
            continue
    return str(s)  # already human-readable, pass through


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")
    return s or "player"


def nat(code):
    """Return (flag_emoji, label) for a nationality code."""
    if not code:
        return ("", "")
    return FLAGS.get(str(code).upper(), ("", str(code)))


def initials(name):
    parts = [p for p in re.split(r"\s+", str(name)) if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def build_rankings(p):
    """Assemble the rankings list. Each entry keeps its OWN as-of date and basis.
    OWGR, ADT OoM, Asian Tour OoM, and WAGR are separate rows — never merged."""
    rows = []
    if p.get("owgr_rank") is not None:
        meta = []
        if p.get("owgr_best") is not None:
            meta.append("best %s" % p["owgr_best"])
        rows.append({
            "label": "OWGR", "full": "Official World Golf Ranking",
            "value": str(p["owgr_rank"]), "meta": meta,
            "as_of": fmt_date(p.get("owgr_as_of")),
        })
    if p.get("adt_oom_pos") is not None:
        rows.append({
            "label": "ADT OoM", "full": "Asian Dev. Tour Order of Merit",
            "value": "#%s" % p["adt_oom_pos"], "meta": [],
            "as_of": fmt_date(p.get("adt_oom_as_of")),
        })
    if p.get("asian_tour_oom_pos") is not None:
        rows.append({
            "label": "Asian Tour OoM", "full": "Asian Tour Order of Merit",
            "value": "#%s" % p["asian_tour_oom_pos"], "meta": [],
            "as_of": fmt_date(p.get("asian_tour_oom_as_of")),
        })
    if p.get("wagr_rank") is not None:
        rows.append({
            "label": "WAGR", "full": "World Amateur Golf Ranking",
            "value": str(p["wagr_rank"]), "meta": [],
            "as_of": fmt_date(p.get("wagr_as_of")),
        })
    return rows


def age_line(p):
    bits = []
    if p.get("birth_date"):
        d = fmt_date(p["birth_date"]) or str(p["birth_date"])
        bits.append(d + (" (age %s)" % p["age"] if p.get("age") is not None else ""))
    elif p.get("birth_year"):
        bits.append(str(p["birth_year"]) + (" (age %s)" % p["age"] if p.get("age") is not None else ""))
    elif p.get("age") is not None:
        bits.append("age %s" % p["age"])
    return bits[0] if bits else None


def win_text(w):
    """A notable_win may be an object {title, tour, year, note} or a plain string."""
    if isinstance(w, str):
        return w, None, None
    title = w.get("title", "")
    year = w.get("year")
    tail = []
    if w.get("tour"):
        tail.append(w["tour"])
    if w.get("note"):
        tail.append(w["note"])
    return title, year, (", ".join(tail) if tail else None)


# --- HTML rendering ---------------------------------------------------------
def render_html(p, theme_name="36media"):
    t = THEMES[theme_name]
    flag, label = nat(p.get("nationality"))
    aka = p.get("also_known_as")
    status = p.get("status", "")
    conf = p.get("in_field_confidence")
    conf_label = CONFIDENCE_LABELS.get(conf, conf)
    rankings = build_rankings(p)

    # header photo / placeholder
    if p.get("photo_url"):
        photo = '<img class="photo" src="%s" alt="%s">' % (e(p["photo_url"]), e(p.get("full_name")))
    else:
        photo = '<div class="photo placeholder">%s</div>' % e(initials(p.get("full_name", "")))

    # subtitle line: flag + nationality + status badge
    sub_bits = []
    if flag or label:
        sub_bits.append('<span class="nat">%s %s</span>' % (flag, e(label)))
    head_badges = ""
    if status:
        cls = "badge badge-am" if str(status).lower().startswith("am") else "badge badge-pro"
        head_badges += '<span class="%s">%s</span>' % (cls, e("Amateur" if str(status).lower().startswith("am") else "Pro"))
    if conf:
        cls = "conf conf-" + e(conf)
        head_badges += '<span class="%s">%s</span>' % (cls, e(conf_label))

    aka_html = '<span class="aka">“%s”</span>' % e(aka) if aka else ""

    # rankings chips
    chips = []
    for r in rankings:
        meta = (" · " + " · ".join(e(m) for m in r["meta"])) if r["meta"] else ""
        asof = e(r["as_of"]) if r["as_of"] else "date n/a"
        chips.append(
            '<div class="rank">'
            '<div class="rank-label" title="%s">%s</div>'
            '<div class="rank-value">%s</div>'
            '<div class="rank-meta">%s</div>'
            '<div class="rank-asof">as of %s</div>'
            '</div>' % (e(r["full"]), e(r["label"]), e(r["value"]), (e(r["full"]) + meta), asof)
        )
    rankings_html = (
        '<section class="block"><h2>Rankings</h2><div class="ranks">%s</div>'
        '<p class="note">Each ranking is dated independently — OWGR, tour Order of Merit, and WAGR measure different populations and are never combined.</p></section>'
        % "".join(chips)
    ) if chips else ""

    # bio definition grid
    bio_rows = []
    al = age_line(p)
    if al:
        bio_rows.append(("Born", al))
    if p.get("turned_pro_year"):
        bio_rows.append(("Turned pro", str(p["turned_pro_year"])))
    if p.get("college"):
        bio_rows.append(("College", p["college"]))
    if p.get("hometown"):
        bio_rows.append(("Hometown", p["hometown"]))
    if p.get("plays"):
        plays = p["plays"]
        bio_rows.append(("Plays", ", ".join(plays) if isinstance(plays, list) else str(plays)))
    bio_html = ""
    if bio_rows:
        items = "".join('<div class="bio-row"><dt>%s</dt><dd>%s</dd></div>' % (e(k), e(v)) for k, v in bio_rows)
        bio_html = '<section class="block"><h2>Bio</h2><dl class="bio">%s</dl></section>' % items

    # career / notable wins
    career_html = ""
    wins = p.get("notable_wins") or []
    if wins or p.get("pro_wins_count") is not None:
        h = "<section class=\"block\"><h2>Career</h2>"
        if p.get("pro_wins_count") is not None:
            h += '<p class="winsline"><strong>%s</strong> career professional win%s.</p>' % (
                e(p["pro_wins_count"]), "" if p["pro_wins_count"] == 1 else "s")
        if wins:
            lis = []
            for w in wins:
                title, year, tail = win_text(w)
                yr = '<span class="yr">%s</span>' % e(year) if year else ""
                tl = ' <span class="wtail">(%s)</span>' % e(tail) if tail else ""
                lis.append('<li>%s<span class="wtitle">%s</span>%s</li>' % (yr, e(title), tl))
            h += '<ul class="wins">%s</ul>' % "".join(lis)
        h += "</section>"
        career_html = h

    # recent form + this-event highlight
    form_html = ""
    if p.get("recent_form") or p.get("this_event"):
        h = '<section class="block"><h2>Recent form</h2>'
        if p.get("recent_form"):
            h += '<p class="form">%s</p>' % e(p["recent_form"])
        te = p.get("this_event")
        if te:
            name = te.get("name") if isinstance(te, dict) else None
            summary = te.get("summary") if isinstance(te, dict) else te
            h += ('<div class="event"><div class="event-name">%s</div><div class="event-sum">%s</div></div>'
                  % (e(name or "This event"), e(summary)))
        h += "</section>"
        form_html = h

    # fun facts
    facts_html = ""
    facts = p.get("fun_facts") or []
    if facts:
        lis = "".join("<li>%s</li>" % e(f) for f in facts)
        facts_html = '<section class="block"><h2>Fun facts</h2><ul class="facts">%s</ul></section>' % lis

    # provenance footer
    prov_bits = []
    if conf:
        src = (" — " + e(p["field_source"])) if p.get("field_source") else ""
        prov_bits.append("Field status: %s%s." % (e(conf_label), src))
    prov_bits.append("Rankings carry per-figure “as of” dates above; re-pull on event week.")
    footer = '<footer class="prov">%s</footer>' % " ".join(prov_bits)

    css = CSS_TEMPLATE.format(**t)
    body = (
        '<article class="card">'
        '<div class="accentbar"></div>'
        '<header class="head">%s<div class="who"><h1>%s%s</h1><div class="subline">%s</div><div class="badges">%s</div></div></header>'
        '%s%s%s%s%s%s'
        '</article>'
    ) % (photo, e(p.get("full_name")), (" " + aka_html if aka_html else ""),
         " ".join(sub_bits), head_badges,
         rankings_html, bio_html, career_html, form_html, facts_html, footer)

    return (
        "<!doctype html>\n<html lang=\"en\"><head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>%s — Player Profile</title>\n%s\n<style>\n%s\n</style>\n</head>\n"
        "<body>\n%s\n</body></html>\n"
    ) % (e(p.get("full_name")), t["font_link"], css, body)


CSS_TEMPLATE = """
:root {{
  --paper: {paper}; --ink: {ink}; --ink2: {ink2}; --accent: {accent};
  --accent-strong: {accent_strong}; --text: {text}; --muted: {muted};
  --tan: {tan}; --line: {line}; --tint: {tint};
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 28px 16px; background: #F3F5F8; color: var(--text);
  font-family: {font}; line-height: 1.5; -webkit-font-smoothing: antialiased; }}
.card {{ max-width: 720px; margin: 0 auto; background: var(--paper);
  border: 1px solid var(--line); border-radius: 16px; overflow: hidden;
  box-shadow: 0 1px 2px rgba(16,36,58,.04), 0 8px 28px rgba(16,36,58,.07); }}
.accentbar {{ height: 6px; background: linear-gradient(90deg, var(--accent-strong), var(--accent)); }}
.head {{ display: flex; gap: 18px; align-items: center; padding: 22px 26px 6px; }}
.photo {{ width: 92px; height: 92px; border-radius: 50%; object-fit: cover;
  border: 3px solid var(--paper); box-shadow: 0 0 0 2px var(--accent); flex: 0 0 auto; }}
.photo.placeholder {{ display: flex; align-items: center; justify-content: center;
  background: var(--tint); color: var(--ink2); font-weight: 800; font-size: 30px; letter-spacing: .5px; }}
.who h1 {{ margin: 0; font-size: 27px; line-height: 1.15; color: var(--ink); font-weight: 800; letter-spacing: -.01em; }}
.who .aka {{ font-size: 18px; font-weight: 600; color: var(--accent-strong); white-space: nowrap; }}
.subline {{ margin-top: 4px; color: var(--muted); font-size: 14.5px; }}
.subline .nat {{ font-weight: 600; color: var(--text); }}
.badges {{ margin-top: 9px; display: flex; flex-wrap: wrap; gap: 7px; }}
.badge {{ font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em;
  padding: 3px 9px; border-radius: 999px; }}
.badge-pro {{ background: var(--tint); color: var(--ink2); }}
.badge-am {{ background: #FBF1E0; color: #9A6B12; }}
.conf {{ font-size: 11.5px; font-weight: 700; padding: 3px 9px; border-radius: 999px; }}
.conf-confirmed-official {{ background: #E9F4EF; color: #227454; }}
.conf-confirmed-press {{ background: #E9F4EF; color: #227454; }}
.conf-notes-only {{ background: #FBF1E0; color: #9A6B12; }}
.conf-unconfirmed {{ background: #FAE9E7; color: #B23B33; }}
.block {{ padding: 16px 26px; border-top: 1px solid var(--line); }}
.block h2 {{ margin: 0 0 12px; font-size: 12.5px; text-transform: uppercase; letter-spacing: .08em;
  color: var(--ink2); font-weight: 700; }}
.ranks {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(118px, 1fr)); gap: 10px; }}
.rank {{ background: var(--tint); border: 1px solid var(--line); border-radius: 12px; padding: 11px 12px; }}
.rank-label {{ font-size: 11.5px; font-weight: 800; color: var(--ink2); text-transform: uppercase; letter-spacing: .04em; }}
.rank-value {{ font-size: 26px; font-weight: 800; color: var(--ink); line-height: 1.1; margin: 2px 0; }}
.rank-meta {{ font-size: 11px; color: var(--muted); min-height: 14px; }}
.rank-asof {{ font-size: 11px; color: var(--muted); margin-top: 5px; font-style: italic; }}
.note {{ font-size: 12px; color: var(--muted); margin: 11px 0 0; }}
dl.bio {{ margin: 0; display: grid; grid-template-columns: 1fr 1fr; gap: 8px 22px; }}
.bio-row dt {{ font-size: 11.5px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); font-weight: 700; }}
.bio-row dd {{ margin: 1px 0 0; font-size: 15px; color: var(--text); font-weight: 500; }}
ul.wins {{ list-style: none; margin: 0; padding: 0; }}
ul.wins li {{ padding: 6px 0; border-bottom: 1px dashed var(--line); font-size: 14.5px; }}
ul.wins li:last-child {{ border-bottom: 0; }}
ul.wins .yr {{ display: inline-block; min-width: 44px; font-weight: 800; color: var(--accent-strong); }}
ul.wins .wtitle {{ font-weight: 600; color: var(--text); }}
ul.wins .wtail {{ color: var(--muted); font-size: 13px; }}
.winsline {{ margin: 0 0 8px; font-size: 14px; color: var(--text); }}
.form {{ margin: 0; font-size: 14.5px; color: var(--text); }}
.event {{ margin-top: 12px; background: var(--tint); border-left: 4px solid var(--accent-strong);
  border-radius: 0 10px 10px 0; padding: 11px 14px; }}
.event-name {{ font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; color: var(--ink2); }}
.event-sum {{ margin-top: 3px; font-size: 14.5px; color: var(--text); }}
ul.facts {{ list-style: none; margin: 0; padding: 0; }}
ul.facts li {{ position: relative; padding: 5px 0 5px 22px; font-size: 14.5px; }}
ul.facts li:before {{ content: "\\26F3"; position: absolute; left: 0; color: var(--accent-strong); }}
.prov {{ padding: 14px 26px 20px; border-top: 1px solid var(--line); font-size: 12px; color: var(--muted); background: #FBFCFD; }}
@media (max-width: 480px) {{
  .head {{ flex-direction: column; text-align: center; }}
  dl.bio {{ grid-template-columns: 1fr; }}
}}
"""


# --- Markdown rendering -----------------------------------------------------
def render_markdown(p):
    out = []
    flag, label = nat(p.get("nationality"))
    title = p.get("full_name", "Player")
    aka = (" “%s”" % p["also_known_as"]) if p.get("also_known_as") else ""
    out.append("# %s%s" % (title, aka))
    subbits = []
    if label:
        subbits.append("%s %s" % (flag, label) if flag else label)
    if p.get("status"):
        subbits.append("Amateur" if str(p["status"]).lower().startswith("am") else "Pro")
    if subbits:
        out.append("_%s_" % " · ".join(subbits))
    conf = p.get("in_field_confidence")
    if conf:
        src = (" — %s" % p["field_source"]) if p.get("field_source") else ""
        out.append("> Field status: **%s**%s" % (CONFIDENCE_LABELS.get(conf, conf), src))
    out.append("")

    rankings = build_rankings(p)
    if rankings:
        out.append("## Rankings")
        out.append("")
        out.append("| Ranking | Position | Detail | As of |")
        out.append("|---|---|---|---|")
        for r in rankings:
            meta = ", ".join(r["meta"]) if r["meta"] else "—"
            out.append("| %s (%s) | %s | %s | %s |" % (
                r["label"], r["full"], r["value"], meta, r["as_of"] or "date n/a"))
        out.append("")
        out.append("_OWGR, tour Order of Merit, and WAGR are separate rankings on different populations — never combined into one number._")
        out.append("")

    bio = []
    al = age_line(p)
    if al:
        bio.append(("Born", al))
    if p.get("turned_pro_year"):
        bio.append(("Turned pro", str(p["turned_pro_year"])))
    if p.get("college"):
        bio.append(("College", p["college"]))
    if p.get("hometown"):
        bio.append(("Hometown", p["hometown"]))
    if p.get("plays"):
        plays = p["plays"]
        bio.append(("Plays", ", ".join(plays) if isinstance(plays, list) else str(plays)))
    if bio:
        out.append("## Bio")
        out.append("")
        for k, v in bio:
            out.append("- **%s:** %s" % (k, v))
        out.append("")

    wins = p.get("notable_wins") or []
    if wins or p.get("pro_wins_count") is not None:
        out.append("## Career")
        out.append("")
        if p.get("pro_wins_count") is not None:
            out.append("**%s** career professional win%s." % (
                p["pro_wins_count"], "" if p["pro_wins_count"] == 1 else "s"))
            out.append("")
        for w in wins:
            t_, yr, tail = win_text(w)
            line = "- "
            if yr:
                line += "**%s** — " % yr
            line += t_
            if tail:
                line += " (%s)" % tail
            out.append(line)
        out.append("")

    if p.get("recent_form") or p.get("this_event"):
        out.append("## Recent form")
        out.append("")
        if p.get("recent_form"):
            out.append(p["recent_form"])
            out.append("")
        te = p.get("this_event")
        if te:
            name = te.get("name") if isinstance(te, dict) else None
            summary = te.get("summary") if isinstance(te, dict) else te
            out.append("**%s** — %s" % (name or "This event", summary))
            out.append("")

    facts = p.get("fun_facts") or []
    if facts:
        out.append("## Fun facts")
        out.append("")
        for f in facts:
            out.append("- %s" % f)
        out.append("")

    out.append("---")
    out.append("_Rankings carry per-figure “as of” dates above; re-pull on event week._")
    return "\n".join(out) + "\n"


# --- driver -----------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="Render a structured golf player record to HTML + Markdown.")
    ap.add_argument("--input", required=True, help="JSON file: a single player object or an array of players.")
    ap.add_argument("--out-dir", default=".", help="Output directory (default: current dir).")
    ap.add_argument("--brand", default="36media", choices=list(THEMES.keys()), help="Brand skin (default 36media).")
    ap.add_argument("--format", default="both", choices=["html", "md", "both"], help="Output format(s).")
    args = ap.parse_args(argv)

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)
    players = data if isinstance(data, list) else [data]

    os.makedirs(args.out_dir, exist_ok=True)
    written = []
    for p in players:
        slug = slugify(p.get("full_name", "player"))
        if args.format in ("html", "both"):
            path = os.path.join(args.out_dir, slug + ".html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(render_html(p, args.brand))
            written.append(path)
        if args.format in ("md", "both"):
            path = os.path.join(args.out_dir, slug + ".md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(render_markdown(p))
            written.append(path)

    for w in written:
        print("wrote %s" % w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
