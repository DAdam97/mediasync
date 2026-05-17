import re

_GLUED_TS_RE = re.compile(r"(?<=[A-Za-z])(\d{1,2}:\d{2}(?::\d{2})?)")
_TS_RE = re.compile(r"^[\[\(]?\d{1,2}:\d{2}(?::\d{2})?[\]\)]?\s*(?:-\s*)?")
_NUM_PREFIX_RE = re.compile(r"^\s*\d{1,3}[.)\]]\s*")
_URL_RE = re.compile(r"https?://\S+")
_EMAIL_RE = re.compile(r"\S+@\S+")
_DOMAIN_RE = re.compile(r"\b[\w-]+\.(?:com|io|net|org|gg|me|tv|co|it|ly|uk|fm)\S*")
_SLASH_PATH_RE = re.compile(r"\s+/\s*\S.*$")
_LABEL_TAG_RE = re.compile(r"\s*\[.*$")
_LEADING_JUNK_RE = re.compile(r"^[^\w'\"(]+", re.UNICODE)


def _is_tracklist_line(line: str) -> bool:
    return bool(re.search(r"\d{1,2}:\d{2}", line) or " - " in line)


def _find_block(lines: list[str]) -> list[str]:
    best: list[str] = []
    current: list[str] = []
    count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue  # blank lines are transparent
        if _is_tracklist_line(stripped):
            current.append(stripped)
            count += 1
        else:
            if count >= 3 and len(current) > len(best):
                best = list(current)
            current = []
            count = 0
    if count >= 3 and len(current) > len(best):
        best = list(current)
    return best


def _process_line(line: str) -> str | None:
    line = _URL_RE.sub("", line)
    line = _EMAIL_RE.sub("", line)
    line = _DOMAIN_RE.sub("", line)
    line = _SLASH_PATH_RE.sub("", line)
    line = _NUM_PREFIX_RE.sub("", line)
    line = _TS_RE.sub("", line)
    line = _LEADING_JUNK_RE.sub("", line)
    line = _LABEL_TAG_RE.sub("", line)
    line = line.strip()
    parts = line.split(" - ", 1)
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        return line
    return None


def _normalize(text: str) -> str:
    text = text.replace("–", "-").replace("—", "-")
    text = _GLUED_TS_RE.sub(r"\n\1", text)
    return text


def parse_tracklist(text: str) -> list[str]:
    text = _normalize(text)
    lines = text.splitlines()
    block = _find_block(lines)
    if not block:
        return []
    results: list[str] = []
    seen: set[str] = set()
    for line in block:
        processed = _process_line(line)
        if processed is None:
            continue
        key = processed.lower().replace(" ", "")
        if key in seen:
            continue
        seen.add(key)
        results.append(processed)
    if len(results) < 3:
        return []
    return results
