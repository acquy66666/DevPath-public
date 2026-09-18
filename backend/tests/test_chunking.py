"""Cutting a lesson into passages the chatbot can quote.

Chunking decides what the RAG half can and cannot answer, and it fails in ways
that look like the model being stupid: a chunk that stops mid-sentence gets
cited as a fragment, a chunk holding two unrelated paragraphs matches both
questions and answers neither, and a chunk over the embedding model's input
limit is silently truncated by the API with no error to notice.

None of this needs a network. The size targets are in tokens, and tokens are
estimated from a ratio measured against Gemini's own `countTokens` -- see
`docs/report/assets/phase-4/embedding-model.txt` -- so the estimate is what is
asserted here, not the true count.
"""

import re

import pytest

from app.services.chunking import (
    CHUNK_OVERLAP_TOKENS,
    MAX_CHUNK_TOKENS,
    TARGET_CHUNK_TOKENS,
    Chunk,
    chunk_text,
    estimate_tokens,
)

# A paragraph of Vietnamese prose, roughly 60 tokens by the estimator.
PARAGRAPH = (
    "Trong Python, biến được tạo ra ngay khi bạn gán giá trị cho nó bằng dấu "
    "bằng. Không cần khai báo kiểu trước khi dùng, và kiểu của một biến có thể "
    "thay đổi về sau. Điều này khiến Python dễ bắt đầu, nhưng cũng là lý do "
    "nhiều lỗi chỉ lộ ra lúc chạy chứ không phải lúc viết."
)


def paragraph(index: int) -> str:
    """One paragraph in which **every sentence** is unique to `index`.

    Not decoration. An earlier version of this file repeated one identical
    paragraph, and the overlap test passed against a chunker that produced no
    overlap at all: every sentence appeared in every chunk, so "a sentence
    from the previous chunk is present" was true by construction. Test data
    that cannot tell two positions apart cannot test a boundary.
    """
    return (
        f"Đoạn số {index}. Trong phần {index}, biến được tạo ra ngay khi bạn "
        f"gán giá trị cho nó bằng dấu bằng. Ở mục {index} không cần khai báo "
        f"kiểu trước khi dùng, và kiểu của một biến có thể thay đổi về sau. "
        f"Ghi chú {index}: điều này khiến Python dễ bắt đầu, nhưng cũng là lý "
        f"do nhiều lỗi chỉ lộ ra lúc chạy chứ không phải lúc viết."
    )


def body(count: int) -> str:
    """`count` distinguishable paragraphs, so a chunk's contents can be traced
    back to where they came from."""
    return "\n\n".join(paragraph(index) for index in range(count))


def test_an_empty_lesson_produces_no_chunks() -> None:
    """A video lesson with no transcript reaches the chunker as an empty
    string. Writing a row for it would put an embedding of nothing into the
    index, and nothing is close to everything."""
    assert chunk_text("") == []
    assert chunk_text("   \n\n  \t ") == []


def test_a_short_lesson_is_one_chunk_and_keeps_its_text_intact() -> None:
    chunks = chunk_text(PARAGRAPH)

    assert len(chunks) == 1
    assert chunks[0].content == PARAGRAPH
    assert chunks[0].index == 0
    assert chunks[0].token_count == estimate_tokens(PARAGRAPH)


def test_chunks_are_numbered_from_zero_without_gaps() -> None:
    """`uq_doc_chunks_lesson_chunk` is on (lesson_id, chunk_index), and the
    retrieval step widens a hit into index-1 and index+1."""
    chunks = chunk_text(body(30))

    assert len(chunks) > 1
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))


def test_no_chunk_exceeds_the_hard_limit() -> None:
    """The soft target is what the splitter aims at; this is the line it may
    not cross, because past it the embedding API truncates in silence."""
    for chunk in chunk_text(body(40)):
        assert chunk.token_count <= MAX_CHUNK_TOKENS, chunk.content[:80]


def test_chunks_are_near_the_target_rather_than_as_small_as_possible() -> None:
    """A splitter that emitted one sentence per chunk would satisfy every test
    above and destroy retrieval: each piece would be too short to carry its own
    context, and the citation would read as a fragment."""
    chunks = chunk_text(body(40))
    full = [chunk for chunk in chunks[:-1]]  # the last one holds the remainder

    assert full, "expected more than one chunk"
    assert min(chunk.token_count for chunk in full) >= TARGET_CHUNK_TOKENS * 0.5


def markers(content: str) -> set[str]:
    """Which numbered paragraphs a chunk contains.

    Asserting overlap by searching for shared *substrings* does not work here
    and the first version of this test proved it: the paragraphs share their
    wording, so any sentence ending is present in every chunk and the search
    succeeds against a chunker with no overlap at all. The markers are the one
    thing that differs between positions, so they are what gets compared.
    """
    return set(re.findall(r"Đoạn số (\d+)\.", content))


def test_consecutive_chunks_overlap() -> None:
    """A sentence answering a question must not fall in the seam between two
    chunks. The overlap is what stops that, and it is the thing most easily
    lost in a rewrite."""
    chunks = chunk_text(body(40))

    assert len(chunks) >= 2
    for earlier, later in zip(chunks, chunks[1:], strict=False):
        shared = markers(earlier.content) & markers(later.content)
        assert shared, (
            f"chunk {later.index} (paragraphs {sorted(markers(later.content))}) "
            f"shares nothing with chunk {earlier.index} "
            f"(paragraphs {sorted(markers(earlier.content))})"
        )


def test_the_overlap_does_not_swallow_the_chunk() -> None:
    """Overlap larger than the step would repeat content forever, and on a
    long lesson that is an infinite loop rather than a bad result."""
    assert CHUNK_OVERLAP_TOKENS < TARGET_CHUNK_TOKENS / 2

    chunks = chunk_text(body(60))
    # Every chunk must advance: the same text twice means no progress.
    assert len({chunk.content for chunk in chunks}) == len(chunks)


def test_a_paragraph_is_not_split_when_it_fits() -> None:
    """Paragraph boundaries are the best split points available in an article,
    so they are preferred over sentence boundaries, which are preferred over
    a blind cut."""
    text = body(3)
    chunks = chunk_text(text)

    assert len(chunks) == 1, "three short paragraphs should fit in one chunk"
    for index in range(3):
        assert f"Đoạn số {index}." in chunks[0].content


def test_a_single_paragraph_longer_than_the_limit_is_still_split() -> None:
    """Transcripts arrive as one wall of text with no blank lines in them. A
    chunker that only split on paragraphs would emit one enormous chunk and
    the API would truncate it."""
    wall = " ".join(f"Câu số {index} nói về một điều gì đó." for index in range(400))

    chunks = chunk_text(wall)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.token_count <= MAX_CHUNK_TOKENS


def test_text_with_no_sentence_breaks_at_all_is_still_cut() -> None:
    """The last resort. A minified file or a transcript with no punctuation
    has no boundary to prefer, and the chunker must still terminate."""
    chunks = chunk_text("x" * (MAX_CHUNK_TOKENS * 20))

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.token_count <= MAX_CHUNK_TOKENS


def test_nothing_is_lost_between_the_chunks() -> None:
    """Overlap means the pieces do not concatenate back to the original, but
    every word of the original has to appear somewhere."""
    text = body(25)
    joined = " ".join(chunk.content for chunk in chunk_text(text))

    for index in range(25):
        assert f"Đoạn số {index}." in joined


@pytest.mark.parametrize(
    "text",
    ["", "   ", "\n\n\n"],
)
def test_estimating_tokens_never_returns_zero_for_a_chunk(text: str) -> None:
    """`ck_doc_chunks_token_count` requires token_count > 0. Empty text never
    reaches a chunk, but the estimator is used elsewhere too."""
    assert estimate_tokens(text) >= 0
    assert estimate_tokens("một từ") >= 1


def test_the_estimate_is_in_the_right_order_of_magnitude() -> None:
    """Measured against Gemini's countTokens: 149 characters of Vietnamese
    prose is 38 real tokens, so the ratio is about 3.9 characters per token.
    The estimator is deliberately more pessimistic than that; what it may not
    be is wrong by a factor that makes the chunk budget meaningless."""
    real_tokens = 38
    estimate = estimate_tokens(
        "Trong Python, biến được tạo ra ngay khi bạn gán giá trị cho nó bằng "
        "dấu bằng. Không cần khai báo kiểu trước khi dùng, và kiểu có thể thay "
        "đổi về sau."
    )

    assert real_tokens <= estimate <= real_tokens * 2


def test_a_chunk_is_stripped_of_the_whitespace_it_was_cut_at() -> None:
    for chunk in chunk_text(body(20)):
        assert chunk.content == chunk.content.strip()
        assert chunk.content, "ck_doc_chunks_content_not_empty"


def test_chunking_is_deterministic() -> None:
    """Re-ingesting a lesson nobody edited must produce the same rows, or every
    re-ingest silently rewrites the whole index."""
    text = body(30)

    assert chunk_text(text) == chunk_text(text)
    assert isinstance(chunk_text(text)[0], Chunk)
