"""Turning an uploaded transcript into the words the chatbot will read.

A `.srt` is mostly not words: cue numbers, timings, formatting tags, and --
from auto-generated captions -- the same line repeated as it scrolls. Every one
of those would land in a chunk and be embedded, and a chunk full of
`00:03:21,440 --> 00:03:24,100` matches every question equally badly.
"""

import pytest

from app.services.transcripts import (
    TranscriptEmptyError,
    TranscriptUnreadableError,
    transcript_format,
    transcript_text,
)

SRT = """1
00:00:01,000 --> 00:00:04,200
Chào các bạn, hôm nay chúng ta học

2
00:00:04,200 --> 00:00:07,900
về biến trong Python.

3
00:00:08,000 --> 00:00:11,500
Một biến là một cái tên
gắn với một giá trị.
"""


# --- Which files are transcripts ---------------------------------------------


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("bai-1.srt", "srt"),
        ("BAI-1.SRT", "srt"),
        ("ghi-chu.txt", "txt"),
        ("bai 1 (final).Txt", "txt"),
        ("phu-de.vtt", None),
        ("bai-1.srt.exe", None),
        ("srt", None),
        ("", None),
    ],
)
def test_the_format_comes_from_the_extension(filename: str, expected: str | None) -> None:
    assert transcript_format(filename) == expected


# --- .srt -------------------------------------------------------------------


def test_cue_numbers_and_timings_are_dropped_and_the_speech_flows_on() -> None:
    """A cue ends wherever the subtitle editor ran out of screen, usually
    mid-sentence. Joined with spaces, the sentences come back whole -- which is
    what the chunker cuts on."""
    assert transcript_text(SRT, "srt") == (
        "Chào các bạn, hôm nay chúng ta học về biến trong Python. "
        "Một biến là một cái tên gắn với một giá trị."
    )


def test_formatting_tags_are_not_words() -> None:
    raw = (
        "1\n00:00:01,000 --> 00:00:02,000\n<i>Nghiêng</i> và <b>đậm</b>\n\n"
        '2\n00:00:02,000 --> 00:00:03,000\n{\\an8}<font color="#ffff00">Trên cùng</font>\n'
    )

    assert transcript_text(raw, "srt") == "Nghiêng và đậm Trên cùng"


def test_windows_line_endings_and_a_byte_order_mark_are_harmless() -> None:
    raw = "\ufeff" + SRT.replace("\n", "\r\n")

    assert transcript_text(raw, "srt") == transcript_text(SRT, "srt")


def test_rolling_auto_captions_are_not_read_twice() -> None:
    """Auto-generated captions scroll: each cue repeats the line before it.
    Kept, every sentence would be embedded twice and weigh twice in retrieval."""
    raw = (
        "1\n00:00:01,000 --> 00:00:02,000\nvòng lặp for\n\n"
        "2\n00:00:02,000 --> 00:00:03,000\nvòng lặp for\nduyệt qua danh sách\n\n"
        "3\n00:00:03,000 --> 00:00:04,000\nduyệt qua danh sách\n"
    )

    assert transcript_text(raw, "srt") == "vòng lặp for duyệt qua danh sách"


def test_timings_with_a_dot_and_without_cue_numbers_are_still_srt() -> None:
    """Not every tool writes the comma, or numbers its cues."""
    raw = "00:00:01.000 --> 00:00:02.500\nMột\n\n00:00:02.500 --> 00:00:04.000\nHai\n"

    assert transcript_text(raw, "srt") == "Một Hai"


def test_an_srt_with_no_timings_is_refused_rather_than_guessed_at() -> None:
    """Most likely a plain text file renamed. Reading it as subtitles would
    silently drop every line that happens to be a number."""
    with pytest.raises(TranscriptUnreadableError):
        transcript_text("Chỉ là một đoạn văn bình thường.\n\n42\n", "srt")


def test_an_srt_with_timings_but_no_speech_is_empty() -> None:
    with pytest.raises(TranscriptEmptyError):
        transcript_text("1\n00:00:01,000 --> 00:00:02,000\n<i></i>\n", "srt")


# --- .txt -------------------------------------------------------------------


def test_a_text_file_keeps_its_paragraphs() -> None:
    """Blank lines are where the chunker prefers to cut, so they stay; runs of
    them and trailing spaces do not carry any meaning and go."""
    raw = "\ufeffĐoạn một.   \r\n\r\n\r\n\r\nĐoạn hai,\r\nvẫn đoạn hai.\r\n\r\n"

    assert transcript_text(raw, "txt") == "Đoạn một.\n\nĐoạn hai,\nvẫn đoạn hai."


def test_a_blank_text_file_is_empty() -> None:
    with pytest.raises(TranscriptEmptyError):
        transcript_text(" \n\n\t\n", "txt")


# --- Either -----------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["srt", "txt"])
def test_a_file_that_was_not_utf8_is_refused(fmt: str) -> None:
    """The browser decodes the file as UTF-8 before sending it, and a
    Windows-1258 subtitle comes out with U+FFFD where every Vietnamese letter
    was. Ingested, the chatbot would quote gibberish -- so it stops here, with
    a message the instructor can act on."""
    raw = "1\n00:00:01,000 --> 00:00:02,000\nCh\ufffdo c\ufffdc b\ufffdn\n"

    with pytest.raises(TranscriptUnreadableError):
        transcript_text(raw, fmt)
