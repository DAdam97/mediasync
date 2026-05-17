from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.downloader import search_and_download, select_best_candidate

_REJECT_WORDS = ["sped up", "slowed", "nightcore", "1 hour", "loop", "karaoke"]


def _candidate(
    id: str = "vid001",
    title: str = "Artist A - Song One",
    uploader: str = "Artist A - Topic",
    duration: int = 200,
) -> dict:
    return {"id": id, "title": title, "uploader": uploader, "duration": duration}


# --- select_best_candidate unit tests (no subprocess) ---


def test_picks_topic_channel_over_generic() -> None:
    topic = _candidate(id="t1", uploader="Artist A - Topic")
    generic = _candidate(id="g1", uploader="SomeUser")
    result = select_best_candidate([generic, topic], blacklist_id="")
    assert result is not None
    assert result["id"] == "t1"


def test_rejects_blacklisted_video_id() -> None:
    bad = _candidate(id="blacklisted_id", uploader="Artist A - Topic")
    good = _candidate(id="good_id", uploader="ArtistChannel")
    result = select_best_candidate([bad, good], blacklist_id="blacklisted_id")
    assert result is not None
    assert result["id"] == "good_id"


def test_rejects_too_short_duration() -> None:
    short = _candidate(id="short", duration=30)
    ok = _candidate(id="ok_id", duration=200)
    result = select_best_candidate([short, ok], blacklist_id="")
    assert result is not None
    assert result["id"] == "ok_id"


def test_rejects_too_long_duration() -> None:
    long_ = _candidate(id="long", duration=700)
    ok = _candidate(id="ok_id", duration=200)
    result = select_best_candidate([long_, ok], blacklist_id="")
    assert result is not None
    assert result["id"] == "ok_id"


@pytest.mark.parametrize("reject_word", _REJECT_WORDS)
def test_rejects_junk_titles(reject_word: str) -> None:
    junk = _candidate(id="junk", title=f"Artist A - Song One ({reject_word})")
    clean = _candidate(id="clean_id")
    result = select_best_candidate([junk, clean], blacklist_id="")
    assert result is not None
    assert result["id"] == "clean_id"


def test_returns_none_when_all_filtered() -> None:
    only = _candidate(id="src", uploader="Artist A - Topic")
    result = select_best_candidate([only], blacklist_id="src")
    assert result is None


def test_falls_back_to_first_when_no_topic_channel() -> None:
    a = _candidate(id="first", uploader="SomeUser")
    b = _candidate(id="second", uploader="AnotherUser")
    result = select_best_candidate([a, b], blacklist_id="")
    assert result is not None
    assert result["id"] == "first"


# --- search_and_download integration (subprocess still mocked) ---


def _make_proc(stdout: bytes = b"", returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, b""))
    return proc


def _json_lines(*candidates: dict) -> bytes:
    import json

    return b"\n".join(json.dumps(c).encode() for c in candidates)


@pytest.mark.asyncio
async def test_raises_when_no_suitable_result() -> None:
    bad = _candidate(id="src", uploader="Artist A - Topic")
    data = _json_lines(bad)

    with patch("asyncio.create_subprocess_exec", return_value=_make_proc(data)):
        with pytest.raises(RuntimeError, match="No suitable result"):
            await search_and_download(
                "Artist A - Song One", blacklist_id="src", media_path="/tmp"
            )
