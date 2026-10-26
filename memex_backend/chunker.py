from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Chunk:
    heading: str | None
    text: str
    chunk_index: int


_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def _units(text: str) -> list[str]:
    """A deterministic whitespace token approximation used for safe chunk sizing."""
    return re.findall(r"\S+", text)


def _split_size(text: str, limit: int, overlap: int) -> list[str]:
    words = _units(text)
    if not words:
        return []
    if len(words) <= limit:
        return [text.strip()]
    step = limit - overlap
    parts = []
    start = 0
    while start < len(words):
        parts.append(" ".join(words[start : start + limit]))
        if start + limit >= len(words):
            break
        start += step
    return parts


def chunk_document(path: str, content: str, max_tokens: int = 512, overlap: int = 64) -> list[Chunk]:
    if max_tokens <= 0 or overlap < 0 or overlap >= max_tokens:
        raise ValueError("max_tokens must be positive and overlap must be smaller than max_tokens")
    if not content.strip():
        return []

    sections: list[tuple[str | None, str]] = []
    if path.lower().endswith(".txt"):
        for para in re.split(r"\n\s*\n", content.strip()):
            if para.strip():
                sections.append((None, para.strip()))
    else:
        heading_stack: list[str] = []
        lines: list[str] = []
        heading: str | None = None

        def flush() -> None:
            body = "\n".join(lines).strip()
            if body:
                sections.append((heading, body))

        for line in content.splitlines():
            match = _HEADING.match(line)
            if match:
                flush()
                level, title = len(match.group(1)), match.group(2).strip()
                heading_stack[:] = heading_stack[: level - 1]
                heading_stack.append(title)
                heading = " > ".join(heading_stack)
                lines = []
            else:
                lines.append(line)
        flush()
        if not sections and content.strip():
            sections.append((None, content.strip()))

    output: list[Chunk] = []
    for heading, section in sections:
        for part in _split_size(section, max_tokens, overlap):
            output.append(Chunk(heading, part, len(output)))
    return output
