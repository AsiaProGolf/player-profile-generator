import json

import pytest

from reference import render_profile


def test_text_date_slug_nationality_and_initial_helpers():
    assert render_profile.e(None) == ""
    assert render_profile.e('<Toby & "Co">') == "&lt;Toby &amp; &quot;Co&quot;&gt;"

    assert render_profile.fmt_date("2026-07-03") == "3 Jul 2026"
    assert render_profile.fmt_date("2026-07") == "Jul 2026"
    assert render_profile.fmt_date("event week") == "event week"
    assert render_profile.fmt_date("") is None

    assert render_profile.slugify("  Sarit Suwannarut!  ") == "sarit-suwannarut"
    assert render_profile.slugify("!!!") == "player"
    assert render_profile.nat("tha") == ("🇹🇭", "Thailand")
    assert render_profile.nat("XYZ") == ("", "XYZ")
    assert render_profile.nat(None) == ("", "")
    assert render_profile.initials("Sarit  Suwannarut") == "SS"
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
        ({"birth_date": "2000-01-02", "age": 26}, "2 Jan 2000 (age 26)"),
        ({"birth_year": 1998, "age": 28}, "1998 (age 28)"),
        ({"age": 21}, "age 21"),
        ({}, None),
    ],
)
def test_age_line_uses_most_specific_available_birth_data(player, expected):
    assert render_profile.age_line(player) == expected


def test_win_text_accepts_plain_and_structured_wins():
    assert render_profile.win_text("Bangkok Classic") == (
        "Bangkok Classic",
        None,
        None,
    )
    assert render_profile.win_text(
        {
            "title": "Thailand Open",
            "year": 2025,
            "tour": "Asian Tour",
            "note": "playoff",
        }
    ) == ("Thailand Open", 2025, "Asian Tour, playoff")
    assert render_profile.win_text({"title": "Club Open"}) == (
        "Club Open",
        None,
        None,
    )


def _rich_player():
    return {
        "full_name": "Ari <Ace> Wong",
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
    assert "<title>Ari &lt;Ace&gt; Wong — Player Profile</title>" in output
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
    output = render_profile.render_html({"full_name": "Jane Doe"})

    assert '<div class="photo placeholder">JD</div>' in output
    assert "<h2>Rankings</h2>" not in output
    assert "<h2>Bio</h2>" not in output
    assert "<h2>Career</h2>" not in output
    assert "<h2>Recent form</h2>" not in output
    assert "<h2>Fun facts</h2>" not in output


def test_render_html_rejects_unknown_theme():
    with pytest.raises(KeyError):
        render_profile.render_html({"full_name": "Jane Doe"}, "unknown")


def test_render_markdown_contains_rich_sections_and_separate_rankings():
    output = render_profile.render_markdown(_rich_player())

    assert output.startswith("# Ari <Ace> Wong “A&W”")
    assert "_🇭🇰 Hong Kong · Amateur_" in output
    assert "| OWGR (Official World Golf Ranking) | 401 | best 350 | 1 Jul 2026 |" in output
    assert "| WAGR (World Amateur Golf Ranking) | 9 | — | 2 Jul 2026 |" in output
    assert "- **College:** Golf & Tech" in output
    assert "**1** career professional win." in output
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
                {"full_name": "Jane Doe", "nationality": "USA"},
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
        "jane-doe.html",
        "jane-doe.md",
        "player.html",
        "player.md",
    ]
    assert "Jane Doe" in (output_dir / "jane-doe.html").read_text(encoding="utf-8")
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
