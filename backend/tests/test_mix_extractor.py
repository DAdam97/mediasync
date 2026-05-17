from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.mix_extractor import extract_tracklist


def _make_proc(stdout: bytes = b"", returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, b""))
    return proc


def _metadata_json(
    chapters: list[dict] | None = None,
    description: str = "",
    comments: list[dict] | None = None,
) -> bytes:
    import json

    data: dict = {"description": description}
    if chapters is not None:
        data["chapters"] = chapters
    if comments is not None:
        data["comments"] = comments
    return json.dumps(data).encode()


@pytest.mark.asyncio
async def test_extract_from_chapters() -> None:
    chapters = [
        {"title": "Artist A - Song One", "start_time": 0},
        {"title": "Artist B - Song Two", "start_time": 120},
        {"title": "Artist C - Song Three", "start_time": 240},
    ]
    metadata = _metadata_json(chapters=chapters)

    with patch("asyncio.create_subprocess_exec", return_value=_make_proc(metadata)):
        result = await extract_tracklist(
            "https://www.youtube.com/watch?v=abc123", fetch_comments=False
        )

    assert result == [
        "Artist A - Song One",
        "Artist B - Song Two",
        "Artist C - Song Three",
    ]


@pytest.mark.asyncio
async def test_extract_from_description_when_chapters_absent() -> None:
    description = """
Feint & Fiction - The Catch
Feint - One Thousand Dreams
Feint - Vision Driver
"""
    metadata = _metadata_json(chapters=None, description=description)

    with patch("asyncio.create_subprocess_exec", return_value=_make_proc(metadata)):
        result = await extract_tracklist(
            "https://www.youtube.com/watch?v=abc123", fetch_comments=False
        )

    assert result == [
        "Feint & Fiction - The Catch",
        "Feint - One Thousand Dreams",
        "Feint - Vision Driver",
    ]


@pytest.mark.asyncio
async def test_extract_from_description_when_chapters_empty() -> None:
    description = """
Feint & Fiction - The Catch
Feint - One Thousand Dreams
Feint - Vision Driver
"""
    metadata = _metadata_json(chapters=[], description=description)

    with patch("asyncio.create_subprocess_exec", return_value=_make_proc(metadata)):
        result = await extract_tracklist(
            "https://www.youtube.com/watch?v=abc123", fetch_comments=False
        )

    assert result == [
        "Feint & Fiction - The Catch",
        "Feint - One Thousand Dreams",
        "Feint - Vision Driver",
    ]


@pytest.mark.asyncio
async def test_extract_from_best_comment_when_description_fails() -> None:
    comments = [
        {"text": "great mix"},
        {"text": "Artist A - Song One\nArtist B - Song Two\nArtist C - Song Three"},
        {"text": "loved it"},
    ]
    metadata = _metadata_json(description="No tracklist here", comments=comments)

    with patch("asyncio.create_subprocess_exec", return_value=_make_proc(metadata)):
        result = await extract_tracklist(
            "https://www.youtube.com/watch?v=abc123", fetch_comments=True
        )

    assert result == [
        "Artist A - Song One",
        "Artist B - Song Two",
        "Artist C - Song Three",
    ]


@pytest.mark.asyncio
async def test_returns_empty_when_all_levels_fail() -> None:
    metadata = _metadata_json(description="No tracklist here.", comments=[])

    with patch("asyncio.create_subprocess_exec", return_value=_make_proc(metadata)):
        result = await extract_tracklist(
            "https://www.youtube.com/watch?v=abc123", fetch_comments=True
        )

    assert result == []


@pytest.mark.asyncio
async def test_raises_on_yt_dlp_failure() -> None:
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=_make_proc(b"", returncode=1),
    ):
        with pytest.raises(RuntimeError, match="yt-dlp"):
            await extract_tracklist("https://www.youtube.com/watch?v=abc123")
