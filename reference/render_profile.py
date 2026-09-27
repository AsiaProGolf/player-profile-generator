#!/usr/bin/env python3
"""player-profile-generator — render a structured golf player record to HTML + Markdown.

Pairs with the sports-data-pipeline skill: that gathers the per-player record,
this renders it into a publish-grade profile page/card for asiaprogolf.com /
36Media public pages and managed athletes. Input = the flat per-player schema
emitted by sports-data-pipeline (see SKILL.md), plus optional profile-enrichment
fields (college, hometown, plays, notable_wins, notable_results, season_stats,
this_event, fun_facts, photo_url, photo_credit, primary_tour).

Design: LIGHT theme by default (light background, dark text). A brand base
(36media / tgh) supplies fonts + navy ink + structure; a per-tour accent overlay
(Asian Tour, ADT, China Tour, All Thailand, ...) tints the accent bar, ranking
chips, win badges and highlights so a field of profiles reads as one family
while each player carries their tour's colour.

Every ranking (OWGR / tour Order-of-Merit / WAGR) renders as its own chip with
its own "as of" date. Rankings are NEVER conflated into one number.

The card CSS lives in CARD_CSS and is the single source of truth for the visual
design — the standalone HTML and the generated Astro component (--emit-astro)
both consume it, so the two cannot drift.

Usage:
    python3 render_profile.py --input player.json
    python3 render_profile.py --input field.json --out-dir out/ --brand 36media --format both
    python3 render_profile.py --input player.json --out-dir out/ --embed-fonts   # faithful offline PDF/PNG render
    python3 render_profile.py --emit-astro web/PlayerProfile.astro               # regenerate the Astro port

`--input` may be a single player object OR an array of players (renders each to
its own slugged file). `--format` = html | md | both (default both).
"""
import argparse
import base64
import html
import json
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")

# --- Brand base skins (both LIGHT) -------------------------------------------
# The brand supplies font + ink (headings stay navy for brand consistency) +
# structural tokens + a DEFAULT accent. When tour_theming is on, the player's
# primary tour overrides accent / accent_strong / tint (see TOUR_ACCENTS).
FONT_STACK = '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Helvetica, Arial, sans-serif'
GOOGLE_INTER = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
)

THEMES = {
    "36media": {
        "label": "36Media / Asia Pro Golf",
        "font": FONT_STACK,
        "font_link": GOOGLE_INTER,
        "tour_theming": True,      # asiaprogolf public profiles get per-tour accents
        "paper": "#ffffff",
        "ink": "#25477A",          # dark navy — headings
        "ink2": "#33649E",         # medium blue — labels
        "text": "#1F2937",         # near-black body
        "muted": "#6B7280",
        "tan": "#A17C5A",
        "line": "#E5E9F0",
        # default accent (sky blue) — used when no tour matches
        "accent": "#7AC8FF",
        "accent_strong": "#33649E",
        "tint": "#EEF5FC",
    },
    "tgh": {
        "label": "Thai Golf Highlights",
        "font": FONT_STACK,
        "font_link": GOOGLE_INTER,
        "tour_theming": False,     # TGH-branded cards keep the fixed TGH identity
        "paper": "#ffffff",
        "ink": "#1B2563",          # deep navy
        "ink2": "#1B2563",
        "text": "#1F2937",
        "muted": "#6B7280",
        "tan": "#A17C5A",
        "line": "#E7E9F2",
        "accent": "#F1A6AE",       # light red (gradient partner)
        "accent_strong": "#C8102E",  # Thai red
        "tint": "#FBEEF0",
    },
}

# --- Per-tour accent overlay (all LIGHT, harmonised mid-saturation) ----------
# Applied over the brand base when the brand opts in (tour_theming). Keys are
# matched case-insensitively against the player's primary tour via TOUR_ALIASES.
TOUR_ACCENTS = {
    "asian_tour":            {"accent_strong": "#B0812F", "accent": "#E7CC86", "tint": "#FAF4E6"},  # gold
    "asian_development_tour":{"accent_strong": "#2F7A4F", "accent": "#93D3AC", "tint": "#EBF6EF"},  # green
    "china_tour":            {"accent_strong": "#C23A32", "accent": "#F0A79F", "tint": "#FCEDEB"},  # red
    "all_thailand_golf_tour":{"accent_strong": "#1F7A8C", "accent": "#86C9D6", "tint": "#E9F5F7"},  # teal
    "pga_tour_americas":     {"accent_strong": "#234E86", "accent": "#9BBBE6", "tint": "#EDF3FB"},  # blue-navy
    "pga_tour":              {"accent_strong": "#1E3A6B", "accent": "#9BB6E0", "tint": "#ECF1FB"},  # navy
    "dp_world_tour":         {"accent_strong": "#12508F", "accent": "#8FC0EE", "tint": "#E9F2FC"},  # blue
    "japan_golf_tour":       {"accent_strong": "#B23140", "accent": "#EBA3AB", "tint": "#FBEDEE"},  # crimson
    "korn_ferry_tour":       {"accent_strong": "#2E6E4E", "accent": "#92CDAE", "tint": "#EBF5EF"},  # green
    "lpga_tour":             {"accent_strong": "#B03A6E", "accent": "#EBA6C4", "tint": "#FBEDF3"},  # rose
    "ladies_european_tour":  {"accent_strong": "#8E44AD", "accent": "#CDA6E0", "tint": "#F4ECFA"},  # violet
}
# alias / substring -> canonical TOUR_ACCENTS key
TOUR_ALIASES = [
    ("asian development tour", "asian_development_tour"), ("adt", "asian_development_tour"),
    ("all thailand golf tour", "all_thailand_golf_tour"), ("all thailand", "all_thailand_golf_tour"),
    ("pga tour americas", "pga_tour_americas"), ("pga tour latinoamerica", "pga_tour_americas"),
    ("korn ferry", "korn_ferry_tour"),
    ("dp world tour", "dp_world_tour"), ("european tour", "dp_world_tour"),
    ("japan golf tour", "japan_golf_tour"), ("jgto", "japan_golf_tour"),
    ("ladies european tour", "ladies_european_tour"), ("let", "ladies_european_tour"),
    ("lpga", "lpga_tour"),
    ("china tour", "china_tour"), ("pgtour china", "china_tour"),
    ("asian tour", "asian_tour"),   # keep last so it doesn't shadow "asian development tour"
    ("pga tour", "pga_tour"),
]

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
    "notes-only": "Notes only — unverified",
    "unconfirmed": "Field entry UNCONFIRMED",
}


# --- helpers ----------------------------------------------------------------
def e(s):
    """HTML-escape, treating None as empty."""
    return html.escape(str(s)) if s is not None else ""


def fmt_date(s):
    """ISO date/month -> human display. Returns None if absent."""
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


def primary_tour(p):
    """Resolve the player's featured tour: explicit primary_tour, else plays[0]."""
    if p.get("primary_tour"):
        return str(p["primary_tour"])
    plays = p.get("plays")
    if isinstance(plays, list) and plays:
        return str(plays[0])
    if isinstance(plays, str) and plays.strip():
        return plays.strip()
    return None


def tour_accent_key(tour_name):
    """Map a tour display name to a TOUR_ACCENTS key, or None."""
    if not tour_name:
        return None
    low = str(tour_name).lower()
    for needle, key in TOUR_ALIASES:
        if needle in low:
            return key
    return None


def resolve_theme(brand, p):
    """Brand base + (optional) per-tour accent overlay. Returns (theme, tour_label)."""
    base = dict(THEMES[brand])
    tour = primary_tour(p)
    if base.get("tour_theming") and tour:
        key = tour_accent_key(tour)
        if key:
            base.update(TOUR_ACCENTS[key])
    return base, tour


def build_rankings(p):
    """Assemble the rankings list. Each entry keeps its OWN as-of date and basis.
    OWGR, ADT OoM, Asian Tour OoM and WAGR are separate rows — never merged."""
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


def age_bio(p):
    """The DOB/age bio row as (label, value).

    Handles age-only data gracefully: when only `age` is known the row is
    labelled "Age" (never "Born: age 23"). Returns None if nothing is known.
    """
    if p.get("birth_date"):
        d = fmt_date(p["birth_date"]) or str(p["birth_date"])
        return ("Born", d + (" · age %s" % p["age"] if p.get("age") is not None else ""))
    if p.get("birth_year"):
        return ("Born", str(p["birth_year"]) + (" · age %s" % p["age"] if p.get("age") is not None else ""))
    if p.get("age") is not None:
        return ("Age", str(p["age"]))
    return None


def win_parts(w):
    """A notable_win may be an object {title, tour, year, note, signature} or a string."""
    if isinstance(w, str):
        return {"title": w, "year": None, "tour": None, "note": None, "signature": False}
    return {
        "title": w.get("title", ""), "year": w.get("year"),
        "tour": w.get("tour"), "note": w.get("note"),
        "signature": bool(w.get("signature")),
    }


def result_parts(r):
    """A notable_result: {finish, title, tour, year} or a string."""
    if isinstance(r, str):
        return {"finish": None, "title": r, "tour": None, "year": None}
    return {"finish": r.get("finish"), "title": r.get("title", ""),
            "tour": r.get("tour"), "year": r.get("year")}


def is_podium(finish):
    """True if a finish string denotes a top-3 (highlight-worthy)."""
    if finish is None:
        return False
    m = re.search(r"\d+", str(finish))
    return bool(m) and int(m.group()) <= 3


# --- HTML fragment builders (shared shape; Astro mirrors these) -------------
def frag_photo(p):
    """Header photo <img> or an intentional monogram tile placeholder."""
    if p.get("photo_url"):
        inner = '<img class="photo" src="%s" alt="%s">' % (e(p["photo_url"]), e(p.get("full_name")))
        if p.get("photo_credit"):
            inner += '<span class="photo-credit">%s</span>' % e(p["photo_credit"])
    else:
        inner = '<div class="photo photo-mono" role="img" aria-label="%s">%s</div>' % (
            e(p.get("full_name", "")), e(initials(p.get("full_name", ""))))
    return '<div class="photo-wrap">%s</div>' % inner


def frag_snapshot(p):
    stats = p.get("season_stats") or []
    if not stats:
        return ""
    tiles = []
    for s in stats:
        if isinstance(s, str):
            continue
        sub = '<div class="ssub">%s</div>' % e(s["sub"]) if s.get("sub") else ""
        tiles.append('<div class="stat"><div class="sval">%s</div><div class="slabel">%s</div>%s</div>' % (
            e(s.get("value", "")), e(s.get("label", "")), sub))
    if not tiles:
        return ""
    return '<section class="block"><h2>Season snapshot</h2><div class="snapshot">%s</div></section>' % "".join(tiles)


def frag_rankings(rankings):
    if not rankings:
        return ""
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
            '</div>' % (e(r["full"]), e(r["label"]), e(r["value"]), (e(r["full"]) + meta), asof))
    return (
        '<section class="block"><h2>Rankings</h2><div class="ranks">%s</div>'
        '<p class="note">OWGR, tour Order of Merit and WAGR rank different populations — each is dated on its own and never combined.</p>'
        '</section>' % "".join(chips))


def frag_bio(p, tour_label):
    rows = []
    ab = age_bio(p)
    if ab:
        rows.append(ab)
    if p.get("turned_pro_year"):
        rows.append(("Turned pro", str(p["turned_pro_year"])))
    if p.get("college"):
        rows.append(("College", str(p["college"])))
    if p.get("hometown"):
        rows.append(("Hometown", str(p["hometown"])))
    if p.get("plays"):
        plays = p["plays"]
        rows.append(("Plays", ", ".join(plays) if isinstance(plays, list) else str(plays)))
    if not rows:
        return ""
    items = "".join('<div class="bio-row"><dt>%s</dt><dd>%s</dd></div>' % (e(k), e(v)) for k, v in rows)
    return '<section class="block"><h2>Bio</h2><dl class="bio">%s</dl></section>' % items


def frag_career(p):
    wins = p.get("notable_wins") or []
    if not wins and p.get("pro_wins_count") is None:
        return ""
    h = '<section class="block"><h2>Career</h2>'
    if p.get("pro_wins_count") is not None:
        n = p["pro_wins_count"]
        h += ('<div class="winspill"><span class="wp-icon">\U0001F3C6</span>'
              '<span class="wp-n">%s</span> professional win%s</div>' % (e(n), "" if n == 1 else "s"))
    if wins:
        rows = []
        for w in wins:
            wp = win_parts(w)
            yr = '<span class="yr">%s</span>' % e(wp["year"]) if wp["year"] else '<span class="yr yr-none">—</span>'
            tour = '<span class="wtour">%s</span>' % e(wp["tour"]) if wp["tour"] else ""
            note = '<div class="wnote">%s</div>' % e(wp["note"]) if wp["note"] else ""
            sig = " win--sig" if wp["signature"] else ""
            star = '<span class="sig-star" title="Signature win">★</span>' if wp["signature"] else ""
            rows.append(
                '<li class="win%s">%s<div class="wbody"><div class="wtop"><span class="wtitle">%s</span>%s%s</div>%s</div></li>'
                % (sig, yr, e(wp["title"]), tour, star, note))
        h += '<ul class="wins">%s</ul>' % "".join(rows)
    h += "</section>"
    return h


def frag_form(p):
    results = p.get("notable_results") or []
    if not (p.get("recent_form") or p.get("this_event") or results):
        return ""
    h = '<section class="block"><h2>Recent form</h2>'
    if results:
        rrows = []
        for r in results:
            rp = result_parts(r)
            cls = "fin fin--podium" if is_podium(rp["finish"]) else "fin"
            fin = '<span class="%s">%s</span>' % (cls, e(rp["finish"])) if rp["finish"] else ""
            tail = []
            if rp["tour"]:
                tail.append(e(rp["tour"]))
            if rp["year"]:
                tail.append(e(rp["year"]))
            meta = '<span class="rmeta">%s</span>' % (" · ".join(tail)) if tail else ""
            rrows.append('<li class="result">%s<span class="rtitle">%s</span>%s</li>' % (
                fin, e(rp["title"]), meta))
        h += '<ul class="results">%s</ul>' % "".join(rrows)
    if p.get("recent_form"):
        h += '<p class="form">%s</p>' % e(p["recent_form"])
    te = p.get("this_event")
    if te:
        name = te.get("name") if isinstance(te, dict) else None
        summary = te.get("summary") if isinstance(te, dict) else te
        result = te.get("result") if isinstance(te, dict) else None
        res = '<div class="event-result">%s</div>' % e(result) if result else ""
        h += ('<div class="event"><div class="event-name">%s</div>%s<div class="event-sum">%s</div></div>'
              % (e(name or "This event"), res, e(summary)))
    h += "</section>"
    return h


def frag_facts(p):
    facts = p.get("fun_facts") or []
    if not facts:
        return ""
    lis = "".join("<li>%s</li>" % e(f) for f in facts)
    return '<section class="block"><h2>Fun facts</h2><ul class="facts">%s</ul></section>' % lis


def frag_footer(p):
    conf = p.get("in_field_confidence")
    bits = []
    if conf:
        conf_label = CONFIDENCE_LABELS.get(conf, conf)
        src = p.get("field_source")
        if src:
            src = str(src).rstrip(" .")  # avoid a double period when the source ends in one
            bits.append("Field status: %s — %s." % (e(conf_label), e(src)))
        else:
            bits.append("Field status: %s." % e(conf_label))
    bits.append("Rankings carry per-figure “as of” dates above; re-pull on event week.")
    return '<footer class="prov">%s</footer>' % " ".join(bits)


def frag_header(p, tour_label):
    flag, label = nat(p.get("nationality"))
    aka = p.get("also_known_as")
    status = p.get("status", "")
    conf = p.get("in_field_confidence")

    sub_bits = []
    if flag or label:
        sub_bits.append('<span class="nat">%s %s</span>' % (flag, e(label)))

    badges = ""
    if status:
        is_am = str(status).lower().startswith("am")
        badges += '<span class="badge %s">%s</span>' % (
            "badge-am" if is_am else "badge-pro", "Amateur" if is_am else "Pro")
    if tour_label:
        badges += '<span class="badge badge-tour">%s</span>' % e(tour_label)
    if conf:
        badges += '<span class="conf conf-%s">%s</span>' % (e(conf), e(CONFIDENCE_LABELS.get(conf, conf)))

    aka_html = ' <span class="aka">“%s”</span>' % e(aka) if aka else ""
    return (
        '<header class="head">%s'
        '<div class="who"><h1>%s%s</h1>'
        '<div class="subline">%s</div>'
        '<div class="badges">%s</div></div></header>'
        % (frag_photo(p), e(p.get("full_name")), aka_html, " ".join(sub_bits), badges))


def build_body(p, brand="36media"):
    """The <article> card — shared shape between standalone HTML and Astro."""
    theme, tour_label = resolve_theme(brand, p)
    return (
        '<article class="card">'
        '<div class="accentbar"></div>'
        '%s%s%s%s%s%s%s%s'
        '</article>'
    ) % (
        frag_header(p, tour_label),
        frag_snapshot(p),
        frag_rankings(build_rankings(p)),
        frag_bio(p, tour_label),
        frag_career(p),
        frag_form(p),
        frag_facts(p),
        frag_footer(p),
    ), theme


# --- CSS (single source of truth for the design) ----------------------------
CSS_VARS = [
    ("--paper", "paper"), ("--ink", "ink"), ("--ink2", "ink2"),
    ("--accent", "accent"), ("--accent-strong", "accent_strong"),
    ("--text", "text"), ("--muted", "muted"), ("--tan", "tan"),
    ("--line", "line"), ("--tint", "tint"),
]


def root_vars(theme, selector=":root"):
    body = "".join("  %s: %s;\n" % (css, theme[key]) for css, key in CSS_VARS)
    body += "  --font: %s;\n" % theme["font"]
    return "%s {\n%s}\n" % (selector, body)


def inline_vars(theme):
    """CSS custom-property string for an inline style= attr (Astro)."""
    return "".join("%s:%s;" % (css, theme[key]) for css, key in CSS_VARS) + "--font:%s;" % theme["font"]


# body/background wrapper — standalone page only (the host page owns <body> in Astro)
PAGE_CSS = """
* { box-sizing: border-box; }
body { margin: 0; padding: 30px 16px; background: #F3F5F8; color: var(--text);
  font-family: var(--font); line-height: 1.5; -webkit-font-smoothing: antialiased; }
"""

# the card itself — consumed verbatim by BOTH the standalone HTML and the Astro port
CARD_CSS = """
.card { max-width: 760px; margin: 0 auto; background: var(--paper); color: var(--text);
  font-family: var(--font); border: 1px solid var(--line); border-radius: 18px; overflow: hidden;
  box-shadow: 0 1px 2px rgba(16,36,58,.05), 0 10px 34px rgba(16,36,58,.08); }
.card h1, .card h2 { font-family: var(--font); }
.accentbar { height: 7px; background: linear-gradient(90deg, var(--accent-strong), var(--accent)); }

/* header */
.head { display: flex; gap: 20px; align-items: center; padding: 24px 28px 8px; }
.photo-wrap { flex: 0 0 96px; width: 96px; display: flex; flex-direction: column; align-items: center; gap: 5px; }
.photo { width: 96px; height: 96px; border-radius: 50%; object-fit: cover; display: block;
  border: 3px solid var(--accent-strong); box-shadow: 0 4px 12px rgba(16,36,58,.14); }
.photo-mono { display: flex; align-items: center; justify-content: center;
  background: linear-gradient(140deg, var(--accent-strong), var(--accent));
  color: #fff; font-weight: 800; font-size: 34px; letter-spacing: .5px;
  text-shadow: 0 1px 2px rgba(0,0,0,.16); }
.photo-credit { font-size: 9.5px; color: var(--muted); max-width: 104px; text-align: center; line-height: 1.25; }
.who { min-width: 0; }
.who h1 { margin: 0; font-size: 28px; line-height: 1.15; color: var(--ink); font-weight: 800; letter-spacing: -.01em; }
.who .aka { font-size: 18px; font-weight: 600; color: var(--accent-strong); white-space: nowrap; }
.subline { margin-top: 5px; color: var(--muted); font-size: 14.5px; }
.subline .nat { font-weight: 600; color: var(--text); }
.badges { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 7px; align-items: center; }
.badge { font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em;
  padding: 3px 10px; border-radius: 999px; }
.badge-pro { background: var(--tint); color: var(--ink2); }
.badge-am { background: #FBF1E0; color: #9A6B12; }
.badge-tour { background: var(--tint); color: var(--accent-strong); border: 1px solid var(--accent-strong);
  text-transform: none; letter-spacing: .01em; }
.conf { font-size: 11.5px; font-weight: 700; padding: 3px 10px; border-radius: 999px; }
.conf-confirmed-official { background: #E9F4EF; color: #227454; }
.conf-confirmed-press { background: #E9F4EF; color: #227454; }
.conf-notes-only { background: #FBF1E0; color: #9A6B12; }
.conf-unconfirmed { background: #FAE9E7; color: #B23B33; }

/* section chrome */
.block { padding: 18px 28px; border-top: 1px solid var(--line); }
.block h2 { margin: 0 0 12px; font-size: 12.5px; text-transform: uppercase; letter-spacing: .08em;
  color: var(--ink2); font-weight: 700; }

/* season snapshot */
.snapshot { display: flex; flex-wrap: wrap; gap: 10px; }
.stat { flex: 1 1 108px; background: var(--tint); border: 1px solid var(--line); border-radius: 12px; padding: 11px 13px; }
.stat .sval { font-size: 22px; font-weight: 800; color: var(--ink); line-height: 1.1; }
.stat .slabel { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em;
  color: var(--ink2); margin-top: 4px; }
.stat .ssub { font-size: 11px; color: var(--muted); margin-top: 1px; }

/* rankings */
.ranks { display: flex; flex-wrap: wrap; gap: 10px; }
.rank { flex: 1 1 132px; background: var(--tint); border: 1px solid var(--line); border-radius: 12px; padding: 12px 13px;
  border-top: 3px solid var(--accent-strong); }
.rank-label { font-size: 11.5px; font-weight: 800; color: var(--accent-strong); text-transform: uppercase; letter-spacing: .04em; }
.rank-value { font-size: 27px; font-weight: 800; color: var(--ink); line-height: 1.1; margin: 3px 0; }
.rank-meta { font-size: 11px; color: var(--muted); min-height: 14px; }
.rank-asof { font-size: 11px; color: var(--muted); margin-top: 5px; font-style: italic; }
.note { font-size: 11.5px; color: var(--muted); margin: 12px 0 0; }

/* bio */
dl.bio { margin: 0; display: flex; flex-wrap: wrap; gap: 12px 24px; }
.bio-row { flex: 1 1 calc(50% - 12px); }
.bio-row dt { font-size: 11.5px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); font-weight: 700; }
.bio-row dd { margin: 2px 0 0; font-size: 15px; color: var(--text); font-weight: 500; }

/* career: wins pill + win rows */
.winspill { display: inline-flex; align-items: baseline; gap: 6px; background: var(--tint);
  border: 1px solid var(--line); border-radius: 999px; padding: 6px 14px 6px 12px; margin: 0 0 14px;
  font-size: 14px; color: var(--ink2); font-weight: 600; }
.winspill .wp-icon { font-size: 15px; }
.winspill .wp-n { font-size: 18px; font-weight: 800; color: var(--ink); }
ul.wins { list-style: none; margin: 0; padding: 0; }
ul.wins li.win { display: flex; gap: 13px; align-items: flex-start; padding: 11px 0; border-bottom: 1px dashed var(--line); }
ul.wins li.win:last-child { border-bottom: 0; }
ul.wins li.win--sig { background: var(--tint); border-left: 3px solid var(--accent-strong);
  border-bottom: 0; border-radius: 0 10px 10px 0; padding: 12px 14px; margin: 2px 0; }
.win .yr { flex: 0 0 auto; min-width: 46px; font-weight: 800; font-size: 14px; color: var(--accent-strong);
  background: var(--tint); border-radius: 8px; padding: 3px 8px; text-align: center; }
.win--sig .yr { background: var(--paper); }
.win .yr-none { color: var(--muted); }
.win .wbody { min-width: 0; }
.win .wtop { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.win .wtitle { font-weight: 700; font-size: 15px; color: var(--text); }
.win .wtour { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .03em;
  color: var(--ink2); background: var(--tint); border-radius: 999px; padding: 2px 9px; }
.win .sig-star { color: var(--accent-strong); font-size: 13px; }
.win .wnote { margin-top: 3px; font-size: 13px; color: var(--muted); }

/* recent form: results, prose, event */
ul.results { list-style: none; margin: 0 0 12px; padding: 0; }
ul.results li.result { display: flex; align-items: baseline; gap: 10px; padding: 6px 0; font-size: 14.5px; }
.result .fin { flex: 0 0 auto; min-width: 40px; text-align: center; font-weight: 800; font-size: 12.5px;
  color: var(--ink2); background: var(--tint); border-radius: 999px; padding: 3px 9px; }
.result .fin--podium { color: #9A6B12; background: #FBF1E0; }
.result .rtitle { font-weight: 600; color: var(--text); }
.result .rmeta { color: var(--muted); font-size: 13px; }
.form { margin: 0; font-size: 14.5px; color: var(--text); }
.event { margin-top: 13px; background: var(--tint); border-left: 4px solid var(--accent-strong);
  border-radius: 0 12px 12px 0; padding: 12px 15px; }
.event-name { font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; color: var(--accent-strong); }
.event-result { margin-top: 3px; font-size: 15px; font-weight: 700; color: var(--ink); }
.event-sum { margin-top: 4px; font-size: 14.5px; color: var(--text); }

/* fun facts */
ul.facts { list-style: none; margin: 0; padding: 0; }
ul.facts li { position: relative; padding: 6px 0 6px 24px; font-size: 14.5px; }
ul.facts li:before { content: "\\26F3"; position: absolute; left: 0; top: 6px; color: var(--accent-strong); }

/* provenance footer */
.prov { padding: 15px 28px 22px; border-top: 1px solid var(--line); font-size: 11.5px; color: var(--muted); background: #FBFCFD; }

@media (max-width: 480px) {
  .head { flex-direction: column; text-align: center; }
  .badges { justify-content: center; }
  dl.bio { grid-template-columns: 1fr; }
}
"""


def font_face_block(embed_fonts):
    """@font-face with vendored Inter TTFs embedded as data URIs.

    Only emitted for --embed-fonts (faithful offline PDF/PNG render). Browsers
    online still get Inter from the Google <link>; this makes WeasyPrint use the
    vendored copy so the render is not a generic-sans fallback.
    """
    if not embed_fonts:
        return ""
    faces = []
    for w in (400, 500, 600, 700, 800):
        path = os.path.join(FONT_DIR, "Inter-%d.ttf" % w)
        if os.path.exists(path):
            with open(path, "rb") as font_file:
                data = base64.b64encode(font_file.read()).decode("ascii")
            faces.append(
                "@font-face { font-family: 'Inter'; font-style: normal; font-weight: %d;"
                " src: url('data:font/ttf;base64,%s') format('truetype'); }" % (w, data))
    return "\n".join(faces) + "\n" if faces else ""


def render_html(p, brand="36media", embed_fonts=False):
    body, theme = build_body(p, brand)
    style = font_face_block(embed_fonts) + root_vars(theme) + PAGE_CSS + CARD_CSS
    return (
        "<!doctype html>\n<html lang=\"en\"><head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>%s — Player Profile</title>\n%s\n<style>\n%s\n</style>\n</head>\n"
        "<body>\n%s\n</body></html>\n"
    ) % (e(p.get("full_name")), theme["font_link"], style, body)


# --- Markdown rendering (kept in sync with the HTML sections) ---------------
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
    tour = primary_tour(p)
    if tour:
        subbits.append(tour)
    if subbits:
        out.append("_%s_" % " · ".join(subbits))
    conf = p.get("in_field_confidence")
    if conf:
        src = p.get("field_source")
        src = (" — %s" % str(src).rstrip(" .")) if src else ""
        out.append("> Field status: **%s**%s" % (CONFIDENCE_LABELS.get(conf, conf), src))
    out.append("")

    stats = p.get("season_stats") or []
    stat_tiles = [s for s in stats if not isinstance(s, str)]
    if stat_tiles:
        out.append("## Season snapshot")
        out.append("")
        for s in stat_tiles:
            sub = " (%s)" % s["sub"] if s.get("sub") else ""
            out.append("- **%s** — %s%s" % (s.get("value", ""), s.get("label", ""), sub))
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
        out.append("_OWGR, tour Order of Merit and WAGR are separate rankings on different populations — never combined into one number._")
        out.append("")

    bio = []
    ab = age_bio(p)
    if ab:
        bio.append(ab)
    if p.get("turned_pro_year"):
        bio.append(("Turned pro", str(p["turned_pro_year"])))
    if p.get("college"):
        bio.append(("College", str(p["college"])))
    if p.get("hometown"):
        bio.append(("Hometown", str(p["hometown"])))
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
            out.append("🏆 **%s** professional win%s." % (
                p["pro_wins_count"], "" if p["pro_wins_count"] == 1 else "s"))
            out.append("")
        for w in wins:
            wp = win_parts(w)
            line = "- "
            if wp["year"]:
                line += "**%s** — " % wp["year"]
            line += wp["title"]
            tail = [x for x in (wp["tour"], wp["note"]) if x]
            if tail:
                line += " (%s)" % ", ".join(tail)
            if wp["signature"]:
                line += " ★"
            out.append(line)
        out.append("")

    results = p.get("notable_results") or []
    if p.get("recent_form") or p.get("this_event") or results:
        out.append("## Recent form")
        out.append("")
        for r in results:
            rp = result_parts(r)
            tail = [str(x) for x in (rp["tour"], rp["year"]) if x]
            fin = ("**%s** — " % rp["finish"]) if rp["finish"] else ""
            line = "- %s%s" % (fin, rp["title"])
            if tail:
                line += " (%s)" % " · ".join(tail)
            out.append(line)
        if results:
            out.append("")
        if p.get("recent_form"):
            out.append(p["recent_form"])
            out.append("")
        te = p.get("this_event")
        if te:
            name = te.get("name") if isinstance(te, dict) else None
            summary = te.get("summary") if isinstance(te, dict) else te
            result = te.get("result") if isinstance(te, dict) else None
            res = (" — %s" % result) if result else ""
            out.append("**%s**%s — %s" % (name or "This event", res, summary))
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


# --- Astro component emitter (single-sources CARD_CSS; cannot fork design) ---
def emit_astro():
    """Return the text of web/PlayerProfile.astro.

    The <style> block is CARD_CSS verbatim (the same string the Python renderer
    uses), and the theme is injected as inline CSS custom properties on the
    article, so the Astro port shares the canonical design and never diverges.
    The frontmatter ports the maps + helpers needed to render from props.
    """
    theme_json = json.dumps({k: v for k, v in THEMES.items()}, indent=2)
    tour_accents_json = json.dumps(TOUR_ACCENTS, indent=2)
    tour_aliases_json = json.dumps(TOUR_ALIASES, indent=2)
    flags_json = json.dumps(FLAGS, ensure_ascii=False, indent=2)
    conf_json = json.dumps(CONFIDENCE_LABELS, indent=2)
    css_vars_json = json.dumps([[c, k] for c, k in CSS_VARS])

    return ASTRO_TEMPLATE % {
        "themes": theme_json,
        "tour_accents": tour_accents_json,
        "tour_aliases": tour_aliases_json,
        "flags": flags_json,
        "conf": conf_json,
        "css_vars": css_vars_json,
        "card_css": CARD_CSS,
    }


# NB: %(...)s are Python format slots; Astro/JS braces are literal.
ASTRO_TEMPLATE = r"""---
/**
 * PlayerProfile.astro — Astro port of the player-profile-generator card.
 *
 * DESIGN SOURCE OF TRUTH: reference/render_profile.py (CARD_CSS + section
 * order). This file is GENERATED by `render_profile.py --emit-astro` — the
 * <style> block below is CARD_CSS verbatim and the theme is injected as inline
 * CSS variables, so the component shares the canonical design and cannot fork.
 * Edit the design in render_profile.py, then regenerate — do not hand-edit CSS.
 *
 * Props:
 *   player : the per-player record (same JSON contract as the CLI renderer).
 *   brand  : "36media" (default) | "tgh".
 *
 * Usage — in a page's frontmatter, import the component + a player record,
 * then place it in the markup:
 *   import PlayerProfile from "../components/PlayerProfile.astro";
 *   import player from "../data/sample-player.json";
 *   // ...then in the template body:
 *   <PlayerProfile player={player} brand="36media" />
 */
export interface Props { player: Record<string, any>; brand?: "36media" | "tgh"; }
const { player: p, brand = "36media" } = Astro.props;

const THEMES: Record<string, any> = %(themes)s;
const TOUR_ACCENTS: Record<string, any> = %(tour_accents)s;
const TOUR_ALIASES: [string, string][] = %(tour_aliases)s;
const FLAGS: Record<string, [string, string]> = %(flags)s;
const CONF: Record<string, string> = %(conf)s;
const CSS_VARS: [string, string][] = %(css_vars)s;

const esc = (s: any) => (s === null || s === undefined) ? "" : String(s);
const nat = (code: any): [string, string] => !code ? ["", ""] : (FLAGS[String(code).toUpperCase()] || ["", String(code)]);
const initials = (name: any) => String(name || "").split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase() || "?";
const MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
function fmtDate(s: any): string | null {
  if (!s) return null;
  let m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s));
  if (m) return `${+m[3]} ${MON[+m[2]-1]} ${m[1]}`;
  m = /^(\d{4})-(\d{2})$/.exec(String(s));
  if (m) return `${MON[+m[2]-1]} ${m[1]}`;
  return String(s);
}
function primaryTour(): string | null {
  if (p.primary_tour) return String(p.primary_tour);
  if (Array.isArray(p.plays) && p.plays.length) return String(p.plays[0]);
  if (typeof p.plays === "string" && p.plays.trim()) return p.plays.trim();
  return null;
}
function tourKey(name: string | null): string | null {
  if (!name) return null;
  const low = name.toLowerCase();
  for (const [needle, key] of TOUR_ALIASES) if (low.includes(needle)) return key;
  return null;
}
const tour = primaryTour();
const theme = { ...THEMES[brand] };
if (theme.tour_theming && tour) { const k = tourKey(tour); if (k) Object.assign(theme, TOUR_ACCENTS[k]); }
const cssVars = CSS_VARS.map(([c, k]) => `${c}:${theme[k]}`).join(";") + `;--font:${theme.font}`;

function buildRankings() {
  const rows: any[] = [];
  if (p.owgr_rank != null) rows.push({ label: "OWGR", full: "Official World Golf Ranking", value: String(p.owgr_rank), meta: p.owgr_best != null ? [`best ${p.owgr_best}`] : [], as_of: fmtDate(p.owgr_as_of) });
  if (p.adt_oom_pos != null) rows.push({ label: "ADT OoM", full: "Asian Dev. Tour Order of Merit", value: `#${p.adt_oom_pos}`, meta: [], as_of: fmtDate(p.adt_oom_as_of) });
  if (p.asian_tour_oom_pos != null) rows.push({ label: "Asian Tour OoM", full: "Asian Tour Order of Merit", value: `#${p.asian_tour_oom_pos}`, meta: [], as_of: fmtDate(p.asian_tour_oom_as_of) });
  if (p.wagr_rank != null) rows.push({ label: "WAGR", full: "World Amateur Golf Ranking", value: String(p.wagr_rank), meta: [], as_of: fmtDate(p.wagr_as_of) });
  return rows;
}
function ageBio(): [string, string] | null {
  if (p.birth_date) { const d = fmtDate(p.birth_date) || String(p.birth_date); return ["Born", d + (p.age != null ? ` · age ${p.age}` : "")]; }
  if (p.birth_year) return ["Born", String(p.birth_year) + (p.age != null ? ` · age ${p.age}` : "")];
  if (p.age != null) return ["Age", String(p.age)];
  return null;
}
const isPodium = (f: any) => { if (f == null) return false; const m = /\d+/.exec(String(f)); return !!m && +m[0] <= 3; };
const winP = (w: any) => typeof w === "string" ? { title: w, year: null, tour: null, note: null, signature: false } : { title: w.title || "", year: w.year, tour: w.tour, note: w.note, signature: !!w.signature };
const resP = (r: any) => typeof r === "string" ? { finish: null, title: r, tour: null, year: null } : { finish: r.finish, title: r.title || "", tour: r.tour, year: r.year };

const [flag, natLabel] = nat(p.nationality);
const isAm = String(p.status || "").toLowerCase().startsWith("am");
const conf = p.in_field_confidence;
const rankings = buildRankings();
const bioRows: [string, string][] = [];
const ab = ageBio(); if (ab) bioRows.push(ab);
if (p.turned_pro_year) bioRows.push(["Turned pro", String(p.turned_pro_year)]);
if (p.college) bioRows.push(["College", String(p.college)]);
if (p.hometown) bioRows.push(["Hometown", String(p.hometown)]);
if (p.plays) bioRows.push(["Plays", Array.isArray(p.plays) ? p.plays.join(", ") : String(p.plays)]);
const wins = (p.notable_wins || []).map(winP);
const results = (p.notable_results || []).map(resP);
const stats = (p.season_stats || []).filter((s: any) => typeof s !== "string");
const facts = p.fun_facts || [];
const te = p.this_event;
const teName = te ? (typeof te === "object" ? te.name : null) : null;
const teSum = te ? (typeof te === "object" ? te.summary : te) : null;
const teRes = te && typeof te === "object" ? te.result : null;
const provSrc = p.field_source ? String(p.field_source).replace(/[ .]+$/, "") : null;
---
<article class="card" style={cssVars}>
  <div class="accentbar"></div>

  <header class="head">
    <div class="photo-wrap">
      {p.photo_url
        ? <span class="photo-slot"><img class="photo" src={p.photo_url} alt={esc(p.full_name)} /></span>
        : <span class="photo-slot"><div class="photo photo-mono" role="img" aria-label={esc(p.full_name)}>{initials(p.full_name)}</div></span>}
      {p.photo_url && p.photo_credit && <span class="photo-credit">{p.photo_credit}</span>}
    </div>
    <div class="who">
      <h1>{esc(p.full_name)}{p.also_known_as && <span class="aka">{`“${p.also_known_as}”`}</span>}</h1>
      <div class="subline">{(flag || natLabel) && <span class="nat">{flag} {natLabel}</span>}</div>
      <div class="badges">
        {p.status && <span class={`badge ${isAm ? "badge-am" : "badge-pro"}`}>{isAm ? "Amateur" : "Pro"}</span>}
        {tour && <span class="badge badge-tour">{tour}</span>}
        {conf && <span class={`conf conf-${conf}`}>{CONF[conf] || conf}</span>}
      </div>
    </div>
  </header>

  {stats.length > 0 &&
    <section class="block"><h2>Season snapshot</h2>
      <div class="snapshot">{stats.map((s: any) =>
        <div class="stat"><div class="sval">{esc(s.value)}</div><div class="slabel">{esc(s.label)}</div>{s.sub && <div class="ssub">{esc(s.sub)}</div>}</div>)}
      </div>
    </section>}

  {rankings.length > 0 &&
    <section class="block"><h2>Rankings</h2>
      <div class="ranks">{rankings.map((r: any) =>
        <div class="rank">
          <div class="rank-label" title={r.full}>{r.label}</div>
          <div class="rank-value">{r.value}</div>
          <div class="rank-meta">{r.full}{r.meta.length ? " · " + r.meta.join(" · ") : ""}</div>
          <div class="rank-asof">as of {r.as_of || "date n/a"}</div>
        </div>)}
      </div>
      <p class="note">OWGR, tour Order of Merit and WAGR rank different populations — each is dated on its own and never combined.</p>
    </section>}

  {bioRows.length > 0 &&
    <section class="block"><h2>Bio</h2>
      <dl class="bio">{bioRows.map(([k, v]) => <div class="bio-row"><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
    </section>}

  {(wins.length > 0 || p.pro_wins_count != null) &&
    <section class="block"><h2>Career</h2>
      {p.pro_wins_count != null &&
        <div class="winspill"><span class="wp-icon">{"\u{1F3C6}"}</span><span class="wp-n">{p.pro_wins_count}</span> professional win{p.pro_wins_count === 1 ? "" : "s"}</div>}
      {wins.length > 0 &&
        <ul class="wins">{wins.map((w: any) =>
          <li class={`win${w.signature ? " win--sig" : ""}`}>
            <span class={`yr${w.year ? "" : " yr-none"}`}>{w.year || "—"}</span>
            <div class="wbody">
              <div class="wtop"><span class="wtitle">{esc(w.title)}</span>{w.tour && <span class="wtour">{w.tour}</span>}{w.signature && <span class="sig-star" title="Signature win">{"★"}</span>}</div>
              {w.note && <div class="wnote">{esc(w.note)}</div>}
            </div>
          </li>)}
        </ul>}
    </section>}

  {(p.recent_form || te || results.length > 0) &&
    <section class="block"><h2>Recent form</h2>
      {results.length > 0 &&
        <ul class="results">{results.map((r: any) =>
          <li class="result">{r.finish && <span class={isPodium(r.finish) ? "fin fin--podium" : "fin"}>{r.finish}</span>}<span class="rtitle">{esc(r.title)}</span>{(r.tour || r.year) && <span class="rmeta">{[r.tour, r.year].filter(Boolean).join(" · ")}</span>}</li>)}
        </ul>}
      {p.recent_form && <p class="form">{esc(p.recent_form)}</p>}
      {te &&
        <div class="event"><div class="event-name">{esc(teName || "This event")}</div>{teRes && <div class="event-result">{esc(teRes)}</div>}<div class="event-sum">{esc(teSum)}</div></div>}
    </section>}

  {facts.length > 0 &&
    <section class="block"><h2>Fun facts</h2>
      <ul class="facts">{facts.map((f: any) => <li>{esc(f)}</li>)}</ul>
    </section>}

  <footer class="prov">
    {conf && <span>Field status: {CONF[conf] || conf}{provSrc ? ` — ${provSrc}` : ""}. </span>}
    Rankings carry per-figure “as of” dates above; re-pull on event week.
  </footer>
</article>

<style>
%(card_css)s
</style>
"""


# --- driver -----------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="Render a structured golf player record to HTML + Markdown.")
    ap.add_argument("--input", help="JSON file: a single player object or an array of players.")
    ap.add_argument("--out-dir", default=".", help="Output directory (default: current dir).")
    ap.add_argument("--brand", default="36media", choices=list(THEMES.keys()), help="Brand skin (default 36media).")
    ap.add_argument("--format", default="both", choices=["html", "md", "both"], help="Output format(s).")
    ap.add_argument("--embed-fonts", action="store_true",
                    help="Inline @font-face to the vendored Inter TTFs — for faithful offline PDF/PNG rendering.")
    ap.add_argument("--emit-astro", metavar="PATH",
                    help="Write the generated Astro component to PATH and exit (single-sources CARD_CSS).")
    args = ap.parse_args(argv)

    if args.emit_astro:
        os.makedirs(os.path.dirname(os.path.abspath(args.emit_astro)), exist_ok=True)
        with open(args.emit_astro, "w", encoding="utf-8") as f:
            f.write(emit_astro())
        print("wrote %s" % args.emit_astro)
        return 0

    if not args.input:
        ap.error("--input is required (unless using --emit-astro)")

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
                f.write(render_html(p, args.brand, embed_fonts=args.embed_fonts))
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
