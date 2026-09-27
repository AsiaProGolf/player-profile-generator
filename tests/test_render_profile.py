import json

import pytest

from reference import render_profile


def test_text_date_slug_nationality_and_initial_helpers():
    assert render_profile.e(None) == ""
    assert render_profile.e('<Example & "Co">') == "&lt;Example &amp; &quot;Co&quot;&gt;"

    assert render_profile.fmt_date("2026-07-03") == "3 Jul 2026"
    assert render_profile.fmt_date("2026-07") == "Jul 2026"
    assert render_profile.fmt_date("event week") == "event week"
    assert render_profile.fmt_date("") is None

    assert render_profile.slugify("  Sample Player!  ") == "sample-player"
    assert render_profile.slugify("!!!") == "player"
    assert render_profile.nat("tha") == ("🇹🇭", "Thailand")
    assert render_profile.nat("XYZ") == ("", "XYZ")
    assert render_profile.nat(None) == ("", "")
    assert render_profile.initials("Sample  Player") == "SP"
    assert render_profile.initials("") == "?"


def test_build_rankings_keeps_every_ranking_and_its_own_date():
    rows = render_profile.build_rankings(
        {
            "owgr_rank": 81,
            "owgr_best": 76,
            "owgr_as_of": "2026-07-01",
            "adt_oom_pos": 0,
            "adt_oom_as_of": "2026-06",
            "asian_tour_oom_pos": 14,
            "asian_tour_oom_as_of": "event week",
            "wagr_rank": 22,
            "wagr_as_of": None,
        }
    )

    assert [row["label"] for row in rows] == [
        "OWGR",
        "ADT OoM",
        "Asian Tour OoM",
        "WAGR",
    ]
    assert [row["value"] for row in rows] == ["81", "#0", "#14", "22"]
    assert [row["as_of"] for row in rows] == [
        "1 Jul 2026",
        "Jun 2026",
        "event week",
        None,
    ]
    assert rows[0]["meta"] == ["best 76"]
    assert render_profile.build_rankings({}) == []


@pytest.mark.parametrize(
    ("player", "expected"),
    [
        ({"birth_date": "2000-01-02", "age": 26}, ("Born", "2 Jan 2000 · age 26")),
        ({"birth_year": 1998, "age": 28}, ("Born", "1998 · age 28")),
        ({"age": 21}, ("Age", "21")),
        ({}, None),
    ],
)
def test_age_bio_uses_most_specific_available_birth_data(player, expected):
    assert render_profile.age_bio(player) == expected


def test_wins_render_plain_and_structured_entries():
    player = {
        "full_name": "Sample Player",
        "notable_wins": [
            "Example Classic",
            {"title": "Example Open", "year": 2025, "tour": "Asian Tour",
             "note": "playoff", "signature": True},
        ],
    }
    html = render_profile.render_html(player)
    markdown = render_profile.render_markdown(player)
    assert "Example Classic" in html
    assert 'class="win win--sig"' in html
    assert "Example Open" in html
    assert "playoff" in html
    assert "- Example Classic" in markdown
    assert "- **2025** — Example Open (Asian Tour, playoff) ★" in markdown


def _rich_player():
    return {
        "full_name": "Sample <Demo> Player",
        "also_known_as": "A&W",
        "nationality": "HKG",
        "status": "Am",
        "in_field_confidence": "confirmed-official",
        "field_source": "Official <field>",
        "photo_url": "https://example.test/p.jpg?x=1&y=2",
        "owgr_rank": 401,
        "owgr_best": 350,
        "owgr_as_of": "2026-07-01",
        "wagr_rank": 9,
        "wagr_as_of": "2026-07-02",
        "birth_date": "2004-05-06",
        "age": 22,
        "college": "Golf & Tech",
        "hometown": "Hong Kong",
        "plays": ["Asian Tour", "ADT"],
        "pro_wins_count": 1,
        "notable_wins": [
            {
                "title": "Open <Final>",
                "year": 2025,
                "tour": "Local Tour",
                "note": "playoff",
            },
            "Invitational",
        ],
        "recent_form": "T2, T8 & T10",
        "this_event": {"name": "Summer Open", "summary": "Leader after R1"},
        "fun_facts": ["Loves <links>", "Speaks three languages"],
    }


def test_render_html_produces_complete_escaped_light_profile():
    output = render_profile.render_html(_rich_player(), "tgh")

    assert output.startswith("<!doctype html>")
    assert "<title>Sample &lt;Demo&gt; Player — Player Profile</title>" in output
    assert 'src="https://example.test/p.jpg?x=1&amp;y=2"' in output
    assert "🇭🇰 Hong Kong" in output
    assert "Amateur" in output
    assert "Confirmed (official)" in output
    assert output.count('class="rank"') == 2
    assert "as of 1 Jul 2026" in output
    assert "as of 2 Jul 2026" in output
    assert "Golf &amp; Tech" in output
    assert "Open &lt;Final&gt;" in output
    assert "Loves &lt;links&gt;" in output
    assert "#C8102E" in output
    assert "<script>" not in output


def test_render_html_minimal_player_uses_initials_and_omits_empty_sections():
    output = render_profile.render_html({"full_name": "Example Player"})

    assert '<div class="photo photo-mono" role="img" aria-label="Example Player">EP</div>' in output
    assert "<h2>Rankings</h2>" not in output
    assert "<h2>Bio</h2>" not in output
    assert "<h2>Career</h2>" not in output
    assert "<h2>Recent form</h2>" not in output
    assert "<h2>Fun facts</h2>" not in output


def test_render_html_rejects_unknown_theme():
    with pytest.raises(KeyError):
        render_profile.render_html({"full_name": "Example Player"}, "unknown")


def test_render_markdown_contains_rich_sections_and_separate_rankings():
    output = render_profile.render_markdown(_rich_player())

    assert output.startswith("# Sample <Demo> Player “A&W”")
    assert "_🇭🇰 Hong Kong · Amateur · Asian Tour_" in output
    assert "| OWGR (Official World Golf Ranking) | 401 | best 350 | 1 Jul 2026 |" in output
    assert "| WAGR (World Amateur Golf Ranking) | 9 | — | 2 Jul 2026 |" in output
    assert "- **College:** Golf & Tech" in output
    assert "**1** professional win." in output
    assert "- **2025** — Open <Final> (Local Tour, playoff)" in output
    assert "**Summer Open** — Leader after R1" in output
    assert "- Loves <links>" in output
    assert output.endswith(
        "_Rankings carry per-figure “as of” dates above; re-pull on event week._\n"
    )


def test_render_markdown_handles_plain_this_event_and_missing_optional_data():
    output = render_profile.render_markdown(
        {"full_name": "Minimal Player", "this_event": "Tied for fifth"}
    )

    assert "**This event** — Tied for fifth" in output
    assert "## Rankings" not in output
    assert "## Bio" not in output
    assert "## Career" not in output


def test_main_renders_batch_to_slugged_html_and_markdown(tmp_path, capsys):
    source = tmp_path / "players.json"
    source.write_text(
        json.dumps(
            [
                {"full_name": "Example Player", "nationality": "USA"},
                {"full_name": "!!!", "recent_form": "Winner"},
            ]
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"

    result = render_profile.main(
        [
            "--input",
            str(source),
            "--out-dir",
            str(output_dir),
            "--brand",
            "36media",
            "--format",
            "both",
        ]
    )

    assert result == 0
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "example-player.html",
        "example-player.md",
        "player.html",
        "player.md",
    ]
    assert "Example Player" in (output_dir / "example-player.html").read_text(encoding="utf-8")
    assert "## Recent form" in (output_dir / "player.md").read_text(
        encoding="utf-8"
    )
    printed = capsys.readouterr().out
    assert printed.count("wrote ") == 4


def test_main_honors_single_requested_format(tmp_path):
    source = tmp_path / "player.json"
    source.write_text(json.dumps({"full_name": "One Player"}), encoding="utf-8")
    output_dir = tmp_path / "out"

    assert render_profile.main(
        [
            "--input",
            str(source),
            "--out-dir",
            str(output_dir),
            "--format",
            "md",
        ]
    ) == 0
    assert (output_dir / "one-player.md").exists()
    assert not (output_dir / "one-player.html").exists()


def test_age_only_profile_has_age_label_in_both_formats():
    player = {"full_name": "Sample Player", "age": 23}
    html = render_profile.render_html(player)
    markdown = render_profile.render_markdown(player)
    assert "<dt>Age</dt><dd>23</dd>" in html
    assert "<dt>Born</dt>" not in html
    assert "- **Age:** 23" in markdown
    assert "**Born:**" not in markdown


def test_snapshot_results_and_current_event_render_in_both_formats():
    player = {
        "full_name": "Sample Player",
        "season_stats": [{"label": "Scoring average", "value": "70.2"}],
        "notable_results": [{"finish": "T2", "title": "Example Open"}],
        "this_event": {"name": "Demo Championship", "summary": "Synthetic result",
                       "result": "R1: 68 (-4)"},
    }
    html = render_profile.render_html(player)
    markdown = render_profile.render_markdown(player)
    assert "<h2>Season snapshot</h2>" in html
    assert 'class="fin fin--podium">T2' in html
    assert 'class="event-result">R1: 68 (-4)' in html
    assert "## Season snapshot" in markdown
    assert "**T2** — Example Open" in markdown
    assert "**Demo Championship** — R1: 68 (-4) — Synthetic result" in markdown
