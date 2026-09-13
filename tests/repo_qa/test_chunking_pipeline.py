"""Chunking pipeline tests — 固定行数策略 + 空块跳过 + 参数校验。"""

import pytest

from repo_qa.chunking import split_text_into_chunks


def test_split_text_into_fixed_size_line_chunks():
    chunks = split_text_into_chunks(
        path="notes.md",
        text="line 1\nline 2\nline 3\nline 4\nline 5\nline 6\nline 7",
        max_lines=3,
    )

    assert [chunk.citation for chunk in chunks] == [
        "notes.md:1-3",
        "notes.md:4-6",
        "notes.md:7-7",
    ]
    assert chunks[1].content == "line 4\nline 5\nline 6"


def test_split_text_skips_blank_only_chunks():
    chunks = split_text_into_chunks(
        path="notes.md",
        text="\n   \n",
        max_lines=1,
    )

    assert chunks == []


def test_split_text_rejects_a_non_positive_chunk_size():
    with pytest.raises(ValueError, match="max_lines"):
        split_text_into_chunks(
            path="notes.md",
            text="line 1",
            max_lines=0,
        )
