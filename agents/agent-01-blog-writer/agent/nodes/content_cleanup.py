"""Small text cleanup helpers shared by Agent 01 nodes."""
from __future__ import annotations


def strip_outer_markdown_fence(text: str) -> str:
    """Remove an accidental outer Markdown code fence from generated prose.

    The blog draft itself should be Markdown, but it should not be wrapped in a
    Markdown code block. Some providers occasionally return:

    ```markdown
    # Title
    ...
    ```

    This helper removes only that outer wrapper and leaves the inner Markdown
    intact.
    """
    cleaned = (text or "").strip()

    while True:
        lines = cleaned.splitlines()
        if len(lines) < 2:
            return cleaned

        opening = lines[0].strip()
        closing = lines[-1].strip()
        if not (_is_markdown_fence_opening(opening) and closing == "```"):
            return cleaned

        cleaned = "\n".join(lines[1:-1]).strip()


def is_markdown_fence_marker(line: str) -> bool:
    stripped = line.strip()
    return stripped == "```" or _is_markdown_fence_opening(stripped)


def _is_markdown_fence_opening(line: str) -> bool:
    stripped = line.strip().lower()
    if not stripped.startswith("```"):
        return False
    language = stripped[3:].strip()
    return language in {"", "markdown", "md"}
