"""Cutting course material into passages small enough to embed and large
enough to quote.

The chatbot answers by finding the nearest chunks to a question and quoting
them back with a link to the lesson. That makes chunk boundaries a retrieval
decision, not a formatting one:

* too small and a chunk cannot carry its own context -- the citation reads as
  a fragment and the model has to guess what it was about;
* too large and one chunk covers several topics, matches every question about
  any of them, and buries the sentence that actually answers;
* and a boundary in the wrong place can put the answering sentence in the seam
  between two chunks, where neither of them retrieves it. That is what the
  overlap is for.

**Split points are preferred, not imposed.** Paragraphs first, because an
article's author already decided where the ideas end; sentences next; and a
blind cut only when the text offers nothing else, which is what a transcript
with no punctuation looks like.

**Token counts here are estimates.** Gemini charges by token and limits by
token, but its tokenizer is server-side: counting exactly would mean an API
call per chunk, which is slower than the embedding it is budgeting for. The
ratio below was measured against `countTokens` on this project's own material
rather than guessed -- see `docs/report/assets/phase-4/embedding-model.txt`.
"""

import re
from dataclasses import dataclass

#: Characters per token, and deliberately below every prose measurement:
#: Vietnamese with diacritics came out at 3.92, without at 3.66, English at
#: 4.26. Erring low makes the estimate an over-count of tokens, so chunks come
#: out slightly under target rather than over the model's input limit.
#:
#: Source code is far denser -- 2.32 -- so a chunk that is mostly code holds
#: more real tokens than this says. That is why MAX_CHUNK_TOKENS sits so far
#: below the model's real 2048-token input limit: the headroom absorbs it.
CHARS_PER_TOKEN = 3.5

#: What the plan asks for: "chunk ~500 token overlap".
TARGET_CHUNK_TOKENS = 500

#: The line a chunk may not cross. Past the model's input limit the API
#: truncates without an error, which would put a half-embedded passage in the
#: index and nothing anywhere to show it happened.
MAX_CHUNK_TOKENS = 700

#: Carried from the end of one chunk into the start of the next. Around 15% of
#: the target: enough that a sentence spanning a boundary survives in one
#: piece somewhere, small enough that the corpus does not grow by a fifth.
CHUNK_OVERLAP_TOKENS = 75

_PARAGRAPH = re.compile(r"\n\s*\n")
# Split *after* the punctuation, so the mark stays with the sentence it ends.
# Vietnamese uses the same sentence-final marks as English.
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class Chunk:
    """One passage, ready to become a `doc_chunks` row."""

    index: int
    content: str
    token_count: int


def estimate_tokens(text: str) -> int:
    """Roughly how many tokens `text` costs. See CHARS_PER_TOKEN."""
    return round(len(text) / CHARS_PER_TOKEN)


def _split_to_pieces(text: str) -> list[str]:
    """The text as the smallest units the chunker will not break further.

    Paragraphs while they fit, sentences inside a paragraph that does not, and
    fixed-width slices inside a sentence that still does not -- a transcript
    can be one unpunctuated paragraph megabytes long, and something has to
    terminate.
    """
    pieces: list[str] = []

    for paragraph in _PARAGRAPH.split(text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if estimate_tokens(paragraph) <= MAX_CHUNK_TOKENS:
            pieces.append(paragraph)
            continue

        for sentence in _SENTENCE.split(paragraph):
            sentence = sentence.strip()
            if not sentence:
                continue
            if estimate_tokens(sentence) <= MAX_CHUNK_TOKENS:
                pieces.append(sentence)
                continue

            width = int(MAX_CHUNK_TOKENS * CHARS_PER_TOKEN)
            pieces.extend(
                sentence[start : start + width]
                for start in range(0, len(sentence), width)
            )

    return pieces


def _tail_within_budget(units: list[str]) -> list[str]:
    """As many trailing `units` as the overlap budget allows, never all of them.

    Never all of them is the load-bearing half: a chunk consisting entirely of
    the previous chunk's tail makes no progress, and on a long lesson that is
    a loop rather than a bad result.
    """
    # Zero means zero. Without this the over-budget fallback below would carry
    # a unit anyway, and the constant would not control the thing it names.
    if CHUNK_OVERLAP_TOKENS <= 0 or len(units) < 2:
        return []

    carried: list[str] = []
    budget = CHUNK_OVERLAP_TOKENS

    # From the end, which is the part the next chunk has to continue from.
    for unit in reversed(units):
        if len(carried) == len(units) - 1:
            break
        cost = estimate_tokens(unit)
        if cost > budget and carried:
            break
        if cost > budget:
            # Nothing whole fits. One unit over budget still beats no overlap:
            # the seam is what this mechanism exists to prevent, and a seam is
            # invisible until a question happens to land on one.
            return [unit]
        carried.insert(0, unit)
        budget -= cost

    return carried


def _overlap_tail(pieces: list[str]) -> list[str]:
    """The end of a finished chunk, to open the next one with.

    Whole pieces where they fit: an overlap cut mid-sentence would reintroduce
    the fragment the pieces exist to avoid.

    The fallback matters more than it looks. A paragraph of ordinary prose runs
    to 80-100 estimated tokens, which is *over* the overlap budget on its own,
    so a version of this that only carried whole pieces carried nothing at all
    and produced chunks that tiled the lesson with no overlap whatsoever. It
    passed its test, because the test data repeated one paragraph and every
    sentence was therefore present in every chunk. Both halves are fixed; this
    is the code half.
    """
    if len(pieces) < 2:
        # One piece, and carrying it would mean the next chunk starts where
        # this one did. A single oversized paragraph gets no overlap -- there
        # is no boundary inside it that the sentence split did not already take.
        return []

    whole = _tail_within_budget(pieces)
    if whole:
        return whole

    sentences = [part.strip() for part in _SENTENCE.split(pieces[-1]) if part.strip()]
    carried = _tail_within_budget(sentences)
    return [" ".join(carried)] if carried else []


def chunk_text(text: str) -> list[Chunk]:
    """Cut `text` into overlapping passages, numbered from zero.

    Deterministic: the same text chunks the same way on every machine and
    every run, which is what makes re-ingesting an unedited lesson a no-op
    instead of a silent rewrite of its rows.
    """
    pieces = _split_to_pieces(text)
    if not pieces:
        return []

    chunks: list[Chunk] = []
    current: list[str] = []
    current_tokens = 0

    def flush() -> list[str]:
        content = "\n\n".join(current).strip()
        if content:
            chunks.append(
                Chunk(
                    index=len(chunks),
                    content=content,
                    token_count=max(1, estimate_tokens(content)),
                )
            )
        return _overlap_tail(current)

    for piece in pieces:
        cost = estimate_tokens(piece)

        # Adding this piece would overshoot the target, and there is already
        # something to keep. Close the chunk and carry its tail forward.
        if current and current_tokens + cost > TARGET_CHUNK_TOKENS:
            carried = flush()
            current = list(carried)
            current_tokens = sum(estimate_tokens(item) for item in carried)

        current.append(piece)
        current_tokens += cost

        # A single piece can still be over the target on its own -- that is
        # what MAX_CHUNK_TOKENS allows for -- so close it immediately rather
        # than letting the next piece push it past the hard limit.
        if current_tokens >= TARGET_CHUNK_TOKENS:
            carried = flush()
            current = list(carried)
            current_tokens = sum(estimate_tokens(item) for item in carried)

    if current and (not chunks or "\n\n".join(current).strip() != chunks[-1].content):
        remainder = "\n\n".join(current).strip()
        # Whatever is left over is pure overlap when it is already contained in
        # the chunk before it; writing it again would be a duplicate row.
        if remainder and (not chunks or remainder not in chunks[-1].content):
            chunks.append(
                Chunk(
                    index=len(chunks),
                    content=remainder,
                    token_count=max(1, estimate_tokens(remainder)),
                )
            )

    return chunks
