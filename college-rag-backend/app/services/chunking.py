"""Layout-aware chunking.

* ~600-800 tokens per chunk (configurable) with ~80-100 tokens of overlap
* chunks never cross a page boundary, so every chunk has an exact page number
* markdown / pipe tables and tab-separated rows are kept together; when a table must
  be split it is split on row boundaries and the header row is repeated
* section titles (markdown headings, numbered or ALL-CAPS headings) are tracked and
  carried across pages so each chunk can get a short context header
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.text import count_tokens

HEADING_MD = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
HEADING_NUM = re.compile(r"^\s*(\d+(?:\.\d+)*\.?)\s+([A-Z\u0900-\u0DFF][^.!?]{2,70})$")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?।])\s+")
PAGEBREAK_MARKERS = ("\f", "<!-- pagebreak -->")


@dataclass
class ChunkDraft:
    page: int | None
    section_title: str | None
    text: str
    index: int = 0


@dataclass
class _Block:
    kind: str  # heading | para | table
    text: str
    header: str | None = None  # table header rows (repeated when splitting)


def split_pages(text: str) -> list[tuple[int | None, str]]:
    """Split plain text into pages on form-feed or ``<!-- pagebreak -->`` markers."""
    for marker in PAGEBREAK_MARKERS[1:]:
        text = text.replace(marker, "\f")
    pages = text.split("\f")
    return [(i + 1, p) for i, p in enumerate(pages) if p.strip()]


def _is_heading(line: str) -> str | None:
    s = line.strip()
    if not s or len(s) > 90:
        return None
    m = HEADING_MD.match(s)
    if m:
        return m.group(1).strip()
    m = HEADING_NUM.match(s)
    if m:
        return s
    letters = [c for c in s if c.isalpha()]
    if len(letters) >= 4 and all(c.isupper() for c in letters if c.isascii()) and s.isascii() and not s.endswith("."):
        return s.title()
    return None


def _is_table_row(line: str) -> bool:
    s = line.strip()
    return (s.startswith("|") and s.count("|") >= 2) or line.count("\t") >= 2


def _blocks(page_text: str) -> list[_Block]:
    blocks: list[_Block] = []
    para: list[str] = []
    table: list[str] = []

    def flush_para():
        if para:
            blocks.append(_Block("para", " ".join(x.strip() for x in para)))
            para.clear()

    def flush_table():
        if table:
            header = None
            if len(table) >= 2 and re.fullmatch(r"\s*\|?[\s:\-|]+\|?\s*", table[1]):
                header = "\n".join(table[:2])
            elif len(table) >= 1:
                header = table[0]
            blocks.append(_Block("table", "\n".join(table), header))
            table.clear()

    for line in page_text.splitlines():
        if _is_table_row(line):
            flush_para()
            table.append(line.rstrip())
            continue
        flush_table()
        if not line.strip():
            flush_para()
            continue
        h = _is_heading(line)
        if h:
            flush_para()
            blocks.append(_Block("heading", h))
            continue
        para.append(line)
    flush_para()
    flush_table()
    return blocks


def _split_long(block: _Block, max_tokens: int) -> list[str]:
    """Split an oversize block: tables by rows (header repeated), prose by sentences."""
    if block.kind == "table":
        rows = block.text.split("\n")
        header_rows = block.header.split("\n") if block.header else []
        body = rows[len(header_rows) :]
        pieces, cur = [], list(header_rows)
        for r in body:
            if count_tokens("\n".join(cur + [r])) > max_tokens and len(cur) > len(header_rows):
                pieces.append("\n".join(cur))
                cur = list(header_rows)
            cur.append(r)
        if len(cur) > len(header_rows):
            pieces.append("\n".join(cur))
        return pieces
    sentences = SENTENCE_SPLIT.split(block.text)
    pieces, cur = [], ""
    for s in sentences:
        if cur and count_tokens(cur + " " + s) > max_tokens:
            pieces.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        pieces.append(cur)
    # a single enormous "sentence": hard split by words
    out: list[str] = []
    for p in pieces:
        if count_tokens(p) <= max_tokens:
            out.append(p)
            continue
        words, cur_w = p.split(), []
        for w in words:
            cur_w.append(w)
            if count_tokens(" ".join(cur_w)) >= max_tokens:
                out.append(" ".join(cur_w))
                cur_w = []
        if cur_w:
            out.append(" ".join(cur_w))
    return out


def _tail(text: str, overlap_tokens: int) -> str:
    """Last few sentences/lines of ``text`` totalling about ``overlap_tokens``."""
    if overlap_tokens <= 0:
        return ""
    units = [u for u in re.split(r"(?<=[.!?।])\s+|\n", text) if u.strip()]
    tail: list[str] = []
    for u in reversed(units):
        if count_tokens(" ".join([u] + tail)) > overlap_tokens and tail:
            break
        tail.insert(0, u)
        if count_tokens(" ".join(tail)) >= overlap_tokens:
            break
    out = " ".join(tail)
    if count_tokens(out) > overlap_tokens * 1.5:  # one giant sentence: keep last words
        out = " ".join(out.split()[-max(1, int(overlap_tokens / 1.3)) :])
    return out


def chunk_pages(
    pages: list[tuple[int | None, str]],
    *,
    max_tokens: int = 700,
    overlap_tokens: int = 90,
    min_tokens_before_section_break: int = 200,
) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    section: str | None = None

    for page_no, page_text in pages:
        cur: list[str] = []
        new_pieces = 0  # pieces added since the last flush (excludes carried overlap)
        cur_section = section

        def flush(carry: bool):
            nonlocal cur, new_pieces
            text = "\n".join(cur).strip()
            if text and new_pieces:
                chunks.append(ChunkDraft(page_no, cur_section, text, len(chunks)))
            cur = [_tail(text, overlap_tokens)] if carry and text else []
            new_pieces = 0

        for block in _blocks(page_text):
            if block.kind == "heading":
                if cur and new_pieces and count_tokens("\n".join(cur)) >= min_tokens_before_section_break:
                    flush(carry=False)
                section = block.text
                if not new_pieces:
                    cur_section = section
                cur.append(block.text)
                new_pieces += 1
                continue
            pieces = [block.text] if count_tokens(block.text) <= max_tokens else _split_long(block, max_tokens)
            for piece in pieces:
                if cur and new_pieces and count_tokens("\n".join(cur + [piece])) > max_tokens:
                    flush(carry=block.kind != "table")
                    cur_section = section
                    # never start a chunk with an overlap that would push it over the limit
                    if cur and count_tokens("\n".join(cur + [piece])) > max_tokens:
                        cur = []
                cur.append(piece)
                new_pieces += 1
        if cur:
            flush(carry=False)
    for i, c in enumerate(chunks):
        c.index = i
    return chunks


def context_header(document_name: str, section_title: str | None, effective_date: str | None = None) -> str:
    parts = [f"Document: {document_name}"]
    if section_title:
        parts.append(f"Section: {section_title}")
    if effective_date:
        parts.append(f"Effective: {effective_date}")
    return " | ".join(parts)
