from __future__ import annotations
from typing import List, Dict, Optional, Tuple
from markdown_it import MarkdownIt
from .chunker import generate_element_id

def _normalize_newlines(md: str) -> str:
    return md.replace("\r\n", "\n").replace("\r", "\n")

def _trim_blank_lines(lines: List[str]) -> List[str]:
    i, j = 0, len(lines)
    while i < j and lines[i].strip() == "":
        i += 1
    while j > i and lines[j - 1].strip() == "":
        j -= 1
    return lines[i:j]

def parse_qa_markdown(md: str) -> List[Dict]:
    """
    Parse a QA markdown document using markdown-it tokens.

    Rules implemented:
      1) Parse into blocks (via MarkdownIt tokens).
      2) Classify each heading:
         - If a heading is immediately followed (ignoring blank lines) by a non-heading block → QUESTION heading.
         - If followed by another heading or EOF → SECTION heading.
      3) Build heading_path from SECTION headings only.
      4) For QUESTION heading, q = heading text (no leading '#').
      5) Answer (a) = all non-heading blocks after the QUESTION heading until the next heading/EOF (markdown preserved).
         - Leading/trailing blank lines trimmed; internal markdown kept intact.
      6) Emit objects with: heading_path, q, a.
      7) Repeat to end.
    """
    src = _normalize_newlines(md)
    src_lines = src.split("\n")

    md_parser = MarkdownIt("gfm-like")
    tokens = md_parser.parse(src)

    # Collect (idx, level, text, start_line) for every heading_open
    headings: List[Tuple[int, int, str, int]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            level = int(tok.tag[1]) if tok.tag and tok.tag.startswith("h") else 1
            # sequence: heading_open, inline(text), heading_close
            text = ""
            if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                text = (tokens[i + 1].content or "").strip()
            start_line = tok.map[0] if tok.map else 0
            headings.append((i, level, text, start_line))
            i += 3  # skip inline + close
            continue
        i += 1

    # Helper: locate the token index right after the heading_close given heading_open index
    def _after_heading_close(idx_open: int) -> int:
        # expects: idx_open (heading_open), idx_open+1 (inline), idx_open+2 (heading_close)
        return idx_open + 3

    # SECTION stack: list of (level, title)
    section_stack: List[Tuple[int, str]] = []

    out_qa: List[Dict] = []

    for h_idx, (tok_idx, level, heading_text, start_line) in enumerate(headings):
        next_tok_idx = _after_heading_close(tok_idx)

        # Find the next significant token after possible blank lines; markdown-it does not emit blank-line tokens,
        # so "immediately followed" is simply "next token exists and is not a heading_open".
        next_is_heading = (next_tok_idx < len(tokens) and tokens[next_tok_idx].type == "heading_open")

        if next_tok_idx >= len(tokens) or next_is_heading:
            # → SECTION heading
            while section_stack and section_stack[-1][0] >= level:
                section_stack.pop()
            section_stack.append((level, heading_text))
            continue

        # Otherwise → QUESTION heading
        q_text = heading_text

        # Determine answer span (lines) from the first real block after this heading until the next heading (or EOF)
        # We'll use line maps to slice the original source (`src_lines`) so markdown is preserved.
        # Start: find first token after heading that has .map
        def _first_block_with_map(idx: int) -> Optional[int]:
            j = idx
            while j < len(tokens):
                if tokens[j].type == "heading_open":
                    return None  # another heading; no answer blocks with map
                if tokens[j].map is not None:
                    return j
                j += 1
            return None

        ans_first_tok = _first_block_with_map(next_tok_idx)
        # If no token with map before the next heading, we still consider any content until next heading as answer,
        # but without precise line boundaries we fallback to using the line after the heading line.
        if ans_first_tok is not None and tokens[ans_first_tok].map is not None:
            ans_start_line = tokens[ans_first_tok].map[0]
        else:
            # Fallback: the line after the heading line
            # NOTE: This still preserves markdown by slicing raw lines.
            # Heading_open.map[0] is the heading line; answer starts at +1.
            ans_start_line = (tokens[tok_idx].map[0] + 1) if tokens[tok_idx].map else start_line + 1

        # End: find next heading_open's start_line (or EOF)
        if h_idx + 1 < len(headings):
            next_heading_start_line = headings[h_idx + 1][3]
            ans_end_line = max(ans_start_line, next_heading_start_line)  # non-inclusive
        else:
            ans_end_line = len(src_lines)

        # Slice and trim
        answer_lines = _trim_blank_lines(src_lines[ans_start_line:ans_end_line])
        a_text = "\n".join(answer_lines)

        qa_obj = {
            "heading_path": [t for (_lvl, t) in section_stack],
            "q": q_text,
            "a": a_text,
        }
        out_qa.append(qa_obj)

    # Convert QA objects to minimal QA blocks for downstream mapping (QA-only chain)
    blocks: List[Dict] = []
    for qa in out_qa:
        eid = generate_element_id({"text": qa["q"] + " || " + qa["a"]}, "qa", heading_path=qa["heading_path"])
        blocks.append({
            "element_id": eid,
            "type": "qa",
            "q": qa["q"],
            "a": qa["a"],
            "heading_path": qa["heading_path"],
            "is_atomic": True,
        })
    return blocks
