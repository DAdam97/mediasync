from services.mix_parser import parse_tracklist


def test_tracklist_without_timestamps() -> None:
    text = """
●Tracklist:
Feint & Fiction - The Catch
Feint - One Thousand Dreams
Feint - Vision Driver
"""
    assert parse_tracklist(text) == [
        "Feint & Fiction - The Catch",
        "Feint - One Thousand Dreams",
        "Feint - Vision Driver",
    ]


def test_glued_timestamps_on_one_line() -> None:
    text = "0:00 - Nosotambejbe - Whispers of the Wind3:28 - Nosotambejbe - Against All Odds7:58 - Nosotambejbe - There's Another Way"  # noqa: E501
    assert parse_tracklist(text) == [
        "Nosotambejbe - Whispers of the Wind",
        "Nosotambejbe - Against All Odds",
        "Nosotambejbe - There's Another Way",
    ]


def test_numbered_bracketed_timestamps_inline_urls() -> None:
    text = """
1.[00:00] Marina and the Diamonds - Immortal (MewOne!, Syberian Beast Remix)  / marina-and-the-diamonds-immortal  # noqa: E501
2.[03:40] Rameses B - We Are One (Ft. Veela)http://smarturl.it/Alchemy2_DL
3.[06:55] Neutralize ft. Emily Underhill - Shining Through The Light
"""
    assert parse_tracklist(text) == [
        "Marina and the Diamonds - Immortal (MewOne!, Syberian Beast Remix)",
        "Rameses B - We Are One (Ft. Veela)",
        "Neutralize ft. Emily Underhill - Shining Through The Light",
    ]


def test_numeric_artist_names_not_truncated() -> None:
    text = """
1. 2Pac - California Love
2. 50 Cent - In Da Club
3. 21 Savage - Bank Account
4. 100 gecs - Money Machine
5. 65daysofstatic - Retreat! Retreat!
"""
    assert parse_tracklist(text) == [
        "2Pac - California Love",
        "50 Cent - In Da Club",
        "21 Savage - Bank Account",
        "100 gecs - Money Machine",
        "65daysofstatic - Retreat! Retreat!",
    ]


def test_false_positive_trap_no_tracklist() -> None:
    text = """
Subscribe to my channel!
Follow me - youtube.com/mychannel
Email - contact@example.com
Discord - discord.gg/abc
"""
    assert parse_tracklist(text) == []


def test_hour_format_timestamps() -> None:
    text = """
1:00:23 Hillsdom - Colours (ft. Novokan3)
1:01:50 Logistics - Been Dreaming (feat. In:Most & Lyra)
1:03:39 Pola & Bryson - Alkaline
1:05:28 Bert H & HumaNature - Blackhouse
"""
    assert parse_tracklist(text) == [
        "Hillsdom - Colours (ft. Novokan3)",
        "Logistics - Been Dreaming (feat. In:Most & Lyra)",
        "Pola & Bryson - Alkaline",
        "Bert H & HumaNature - Blackhouse",
    ]


def test_numbered_no_timestamps_trailing_label_tags() -> None:
    text = """
Track List :

01. Paul Van Dyk with Aly and Fila ft. Sue Mclaren - Guardian (Sunset Mix)[ Ultra ]

02. Headstrong feat. Stine Grove - Love Until It Hurts (Aurosonic Progressive Mix)[ Sola Records ]  # noqa: E501

03. Rex Mundi feat. Susana - Nothing At All (Original Mix)[ Coldharbour Recordings ]
"""
    assert parse_tracklist(text) == [
        "Paul Van Dyk with Aly and Fila ft. Sue Mclaren - Guardian (Sunset Mix)",
        "Headstrong feat. Stine Grove - Love Until It Hurts (Aurosonic Progressive Mix)",  # noqa: E501
        "Rex Mundi feat. Susana - Nothing At All (Original Mix)",
    ]


def test_blank_lines_between_every_entry() -> None:
    text = """
Artist A - Song One

Artist B - Song Two

Artist C - Song Three

Artist D - Song Four
"""
    assert parse_tracklist(text) == [
        "Artist A - Song One",
        "Artist B - Song Two",
        "Artist C - Song Three",
        "Artist D - Song Four",
    ]
