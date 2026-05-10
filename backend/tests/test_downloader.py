import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.downloader import run_download


def _make_proc(stdout: bytes = b"", returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, b""))
    return proc


def _output_arg(args: tuple) -> str:
    idx = list(args).index("--output")
    return args[idx + 1]


def _mutagen_patches():
    easy_id3 = MagicMock()
    easy_id3.return_value.get.return_value = [""]
    mp3_tag = MagicMock()
    mp3_tag.return_value.info.length = 180.0
    mods = {
        "mutagen": MagicMock(),
        "mutagen.easyid3": MagicMock(EasyID3=easy_id3),
        "mutagen.mp3": MagicMock(MP3=mp3_tag),
    }
    return patch.dict(sys.modules, mods)


@pytest.mark.asyncio
async def test_youtube_url_uses_title_only_template(tmp_path: Path) -> None:
    fake_mp3 = tmp_path / "music" / "NF - The Search.mp3"
    fake_mp3.parent.mkdir(parents=True)
    fake_mp3.write_bytes(b"fake")

    proc = _make_proc(stdout=str(fake_mp3).encode())

    with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec, _mutagen_patches():
        await run_download(1, "https://www.youtube.com/watch?v=abc123", str(tmp_path))

    args = mock_exec.call_args[0]
    template = _output_arg(args)
    assert "%(title)s" in template
    assert "%(artist)s" not in template


@pytest.mark.asyncio
async def test_youtube_music_url_uses_artist_title_template(tmp_path: Path) -> None:
    fake_mp3 = tmp_path / "music" / "NF - The Search.mp3"
    fake_mp3.parent.mkdir(parents=True)
    fake_mp3.write_bytes(b"fake")

    proc = _make_proc(stdout=str(fake_mp3).encode())

    with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec, _mutagen_patches():
        await run_download(
            1, "https://music.youtube.com/watch?v=abc123", str(tmp_path)
        )

    args = mock_exec.call_args[0]
    template = _output_arg(args)
    assert "%(artist)s" in template
    assert "%(title)s" in template
