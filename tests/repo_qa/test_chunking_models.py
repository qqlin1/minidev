"""Chunk schema tests — ① Schema 契约与 citation。"""

import pytest

from repo_qa.chunking import Chunk


def test_chunk_exposes_a_citeable_source_location():
    chunk = Chunk(
        path="agent/runtime/v0.py",
        start_line=10,
        end_line=20,
        content="def run_turn():\n    pass",
    )

    assert chunk.citation == "agent/runtime/v0.py:10-20"


@pytest.mark.parametrize(
    ("path", "start_line", "end_line", "content", "message"),
    [
        ("", 1, 1, "text", "path"),
        ("file.py", 0, 1, "text", "start_line"),
        ("file.py", 3, 2, "text", "end_line"),
        ("file.py", 1, 1, "   ", "content"),
    ],
)
def test_chunk_rejects_invalid_data(
    path: str,
    start_line: int,
    end_line: int,
    content: str,
    message: str,
):
    with pytest.raises(ValueError, match=message):
        Chunk(
            path=path,
            start_line=start_line,
            end_line=end_line,
            content=content,
        )
