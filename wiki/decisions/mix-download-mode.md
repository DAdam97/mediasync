---
title: Mix Download Mode
type: decision
related: [issues.md, yt-dlp.md]
updated: 2026-05-17
---

# Mix Download Mode

## What it is

`mode=mix` in `POST /api/downloads` — the user submits a long YouTube mix/compilation URL. The system extracts the tracklist from the video metadata, then searches YouTube for each individual track and downloads them separately as MP3s. The original mix video is never split or downloaded.

Primary use case: collecting diverse individual tracks for the #7 ML dataset.

## Key decisions

### Integration
Built into the existing `backend/` — new `mode=mix` branch in `POST /api/downloads`. Reuses the existing `downloads` table, download manager, and downloader. No separate microservice.

### Name
`mix` — consistent with existing mode names (`track`, `playlist`, `discovery`).

### Shazam fallback
Out of scope for v1. The 3-level cascade (chapters → description → comments) covers all realistic dataset-collection use cases. Shazam would add `shazamio` dependency + ffmpeg chunking + minutes of processing time.

### Cascade levels (in order, stops at first success)

1. **YouTube chapters** — yt-dlp metadata, if the video has proper chapters with timestamps
2. **Description parsing** — regex-based tracklist extraction from the video description
3. **Comment parsing** — top comments scanned for tracklist (only fetched if description fails)

### Download strategy
For each `"Artist - Title"` string found by the cascade:
1. `yt-dlp -j "ytsearch5:Artist - Title"` — fetch 5 candidates as JSON
2. Filter candidates:
   - Prefer `uploader` ending in `- Topic` (YouTube auto-generated official releases)
   - Reject duration < 60s or > 600s
   - Reject titles containing: "sped up", "slowed", "nightcore", "1 hour", "loop", "karaoke"
   - **Blacklist the source mix video ID** — prevents the original mix from being downloaded again
3. Download the best match with existing `run_download(url)`

### Extraction timing
Synchronous — `POST /api/downloads` waits for the cascade to complete before returning. Chapters + description parse: < 1s. Comment fetch: max ~15s. Acceptable for this use case.

### Error handling

| Situation | Behaviour |
|---|---|
| No tracklist found (all 3 levels fail) | 1 `error` record: `"No tracklist found for: <video title>"` |
| Track found in tracklist but no YouTube result | `error` record per track: `"No suitable result found on YouTube"` |
| Track found but only result is the source mix | Same as above (blacklisted) |

### Parser algorithm (`mix_parser.py`)

1. **Normalization**: en-dash/em-dash → hyphen, remove URLs, split glued timestamps
2. **Contiguous block detection**: sliding counter — 3+ consecutive lines matching tracklist pattern (has timestamp OR has ` - `) → identified as tracklist block. Blank lines are transparent (do not reset the counter) to handle tracklists with empty lines between each entry. Prevents false positives from social links like `Follow me - youtube.com/channel`.
3. **Per-line processing** on the detected block:
   - Remove timestamp: `\[?\d{1,2}:\d{2}(?::\d{2})?\]?` (handles `3:45`, `1:03:45`, `[00:00]`)
   - Remove number prefix **only** if unambiguous list marker: `^\s*\d{1,3}[\.\)\]]\s+`
   - Strip leading emoji/bullet chars from line start
   - **Strip trailing label tags**: `re.sub(r'\s*\[.*$', '', line)` — removes `[ Ultra ]`, `[ Coldharbour Recordings ]`, and unclosed `[ Beat Service Audio (RazNitzanMusic` from the end of the line
   - Accept only lines containing ` - ` with non-empty text on both sides
4. **Deduplication** by normalized key: `lower().replace(" ", "")`
5. **Sanity check**: < 3 results → return `[]`, cascade continues

Handled timestamp formats: `3:45`, `03:45`, `1:03:45`, `[00:00]`, `(1:23:45)`  
Handled prefixes: `1.`, `2)`, `[3]`, `●`, `▶`, `🎵`, emojis  
Handled separators: ` - `, ` – ` (en-dash), ` — ` (em-dash, normalized)  
NOT handled (v1 out of scope): `:` or `|` as separator, artist and title on separate lines

### Comment selection
When comments are needed: score each comment by counting tracklist-pattern lines, pick the highest-scoring comment. Not the first comment.

## Implementation plan

### New files
- `backend/services/mix_parser.py` — tracklist parser
- `backend/services/mix_extractor.py` — cascade orchestrator + yt-dlp metadata fetch
- `backend/tests/test_mix_parser.py` — 8 parser test cases (see below)

### Modified files
- `backend/services/downloader.py` — add `search_and_download(query, blacklist_id)`
- `backend/routers/downloads.py` — add `mode=mix` branch
- `backend/services/download_manager.py` — wire mix mode

### No new dependencies
yt-dlp and mutagen already present. No shazamio needed.

### Suggested implementation order (TDD)
1. `mix_parser.py` + `test_mix_parser.py` — all 5 test cases green before touching anything else
2. `mix_extractor.py` — metadata fetch (yt-dlp `--dump-json`) + cascade orchestrator
3. `downloader.py` — `search_and_download(query, blacklist_id)` function
4. Wire into `routers/downloads.py` + `download_manager.py`

## Parser test cases (must all pass)

```python
# Case 1: tracklist without timestamps
input = """
●Tracklist:
Feint & Fiction - The Catch
Feint - One Thousand Dreams
Feint - Vision Driver
"""
expected = ['Feint & Fiction - The Catch', 'Feint - One Thousand Dreams', 'Feint - Vision Driver']

# Case 2: glued timestamps on one line
input = "0:00 - Nosotambejbe - Whispers of the Wind3:28 - Nosotambejbe - Against All Odds7:58 - Nosotambejbe - There's Another Way"
expected = ['Nosotambejbe - Whispers of the Wind', 'Nosotambejbe - Against All Odds', "Nosotambejbe - There's Another Way"]

# Case 3: numbered list, bracketed timestamps, inline URLs
input = """
1.[00:00] Marina and the Diamonds - Immortal (MewOne!, Syberian Beast Remix)  / marina-and-the-diamonds-immortal
2.[03:40] Rameses B - We Are One (Ft. Veela)http://smarturl.it/Alchemy2_DL
3.[06:55] Neutralize ft. Emily Underhill - Shining Through The Light
"""
expected = ['Marina and the Diamonds - Immortal (MewOne!, Syberian Beast Remix)', 'Rameses B - We Are One (Ft. Veela)', 'Neutralize ft. Emily Underhill - Shining Through The Light']

# Case 4: numeric artist names — must NOT be truncated
input = """
1. 2Pac - California Love
2. 50 Cent - In Da Club
3. 21 Savage - Bank Account
4. 100 gecs - Money Machine
5. 65daysofstatic - Retreat! Retreat!
"""
expected = ['2Pac - California Love', '50 Cent - In Da Club', '21 Savage - Bank Account', '100 gecs - Money Machine', '65daysofstatic - Retreat! Retreat!']

# Case 5: false positive trap — no tracklist present
input = """
Subscribe to my channel!
Follow me - youtube.com/mychannel
Email - contact@example.com
Discord - discord.gg/abc
"""
expected = []  # no 3+ consecutive tracklist lines in a contiguous block

# Case 6: hour-format timestamps (real-world DnB mix)
input = """
1:00:23 Hillsdom - Colours (ft. Novokan3)
1:01:50 Logistics - Been Dreaming (feat. In:Most & Lyra)
1:03:39 Pola & Bryson - Alkaline
1:05:28 Bert H & HumaNature - Blackhouse
"""
expected = ['Hillsdom - Colours (ft. Novokan3)', 'Logistics - Been Dreaming (feat. In:Most & Lyra)', 'Pola & Bryson - Alkaline', 'Bert H & HumaNature - Blackhouse']

# Case 7: numbered list, no timestamps, trailing [Label] tags (trance mix format)
input = """
Track List :

01. Paul Van Dyk with Aly and Fila ft. Sue Mclaren - Guardian (Sunset Mix)[ Ultra ]

02. Headstrong feat. Stine Grove - Love Until It Hurts (Aurosonic Progressive Mix)[ Sola Records ]

03. Rex Mundi feat. Susana - Nothing At All (Original Mix)[ Coldharbour Recordings ]
"""
expected = [
    'Paul Van Dyk with Aly and Fila ft. Sue Mclaren - Guardian (Sunset Mix)',
    'Headstrong feat. Stine Grove - Love Until It Hurts (Aurosonic Progressive Mix)',
    'Rex Mundi feat. Susana - Nothing At All (Original Mix)',
]

# Case 8: blank lines between every entry
input = """
Artist A - Song One

Artist B - Song Two

Artist C - Song Three

Artist D - Song Four
"""
expected = ['Artist A - Song One', 'Artist B - Song Two', 'Artist C - Song Three', 'Artist D - Song Four']
```
