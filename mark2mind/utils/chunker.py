import contextlib
import io
import json
import hashlib
import re
import os
from pathlib import Path
from typing import List
#Silence tokenizer warning on import
with contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(
    io.StringIO()
) as stderr:
    from transformers import AutoTokenizer
    from transformers import logging as token_logger

    token_logger.set_verbosity_error()
from markdown_it import MarkdownIt
from slugify import slugify
import uuid
import spacy

# Load once (globally to avoid reloading per call)
try:
    _spacy_nlp = spacy.load("en_core_web_sm")
except OSError:
    raise RuntimeError("You must run: python -m spacy download en_core_web_sm")

def semantic_split_spacy(text, max_tokens, tokenizer):
    doc = _spacy_nlp(text)
    chunks = []
    current = ""
    for sent in doc.sents:
        proposed = current + " " + sent.text if current else sent.text
        if len(tokenizer.encode(proposed)) > max_tokens:
            if current:
                chunks.append(current.strip())
            current = sent.text
        else:
            current = proposed
    if current:
        chunks.append(current.strip())
    return chunks

def _normalize_for_id(s: str) -> str:
    """
    Normalize text for stable hashing:
    - strip leading/trailing whitespace
    - collapse all internal whitespace to a single space
    """
    if not s:
        return ""
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s

def _hash8(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]

def generate_element_id(block, prefix, heading_path=None):
    """
    Deterministic ID based on content (optionally content + heading path).
    By default we hash ONLY content so identical elements get the same ID across contexts.

    Set env MARK2MIND_ID_SCOPE to:
      - "content"         (default) => identical content => same ID
      - "content+path"    => include heading_path in the hash (keeps duplicates if placed under different headings)
    """
    import os
    scope = os.getenv("MARK2MIND_ID_SCOPE", "content")

    # choose the most representative payload per type
    content = ""
    if isinstance(block, dict):
        # tables & paragraphs put text in "text"; code uses "text"; images use "src" (fallback to alt)
        if block.get("type") == "image":
            content = block.get("src") or block.get("alt") or ""
        else:
            content = block.get("text") or block.get("markdown") or block.get("alt") or ""
    else:
        # in parse() we sometimes pass a small attrs dict for images
        content = (block.get("src") if isinstance(block, dict) else "") or ""

    norm = _normalize_for_id(content)

    if scope == "content+path" and heading_path:
        path_norm = _normalize_for_id(" / ".join(heading_path))
        payload = f"{norm} || {path_norm}"
    else:
        payload = norm

    slug = slugify(norm)[:8] or "item"
    h = _hash8(payload)
    return f"{prefix}_{slug}_{h}"

def parse_markdown_as_tree(md_text: str):
    md = MarkdownIt("gfm-like")
    tokens = md.parse(md_text)

    root = {"type": "root", "children": []}
    stack = [(0, root)]  # (level, node)
    i = 0

    def get_heading_path(stack):
        return [n["text"] for lvl, n in stack if n["type"] == "heading"]

    def add_child_to_parent(level, block):
        # Find closest parent with lower level
        level = max(1, min(level, stack[-1][0] + 1))
        while stack and stack[-1][0] >= level and stack[-1][0] > 0:
            stack.pop()

        parent = stack[-1][1]
        parent.setdefault("children", []).append(block)
        return parent

    while i < len(tokens):
        token = tokens[i]

        if token.type == "heading_open":
            level = int(token.tag[1])
            heading_text = tokens[i + 1].content.strip()
            block = {
                "type": "heading",
                "level": level,
                "text": heading_text,
                "element_id": generate_element_id({"text": heading_text}, "heading", heading_path=get_heading_path(stack) + [heading_text]),
                "children": []
            }
            parent = add_child_to_parent(level, block)
            stack.append((level, block))
            i += 3
            block["heading_path"] = get_heading_path(stack)


        elif token.type == "paragraph_open":
            inline_token = tokens[i + 1]
            if inline_token.type == "inline" and inline_token.children:
                # Extract image(s)
                for child in inline_token.children:
                    if child.type == "image":
                        block = {
                            "type": "image",
                            "alt": child.attrs.get("alt", ""),
                            "src": child.attrs["src"],
                            "element_id": generate_element_id(child.attrs, "image", heading_path=get_heading_path(stack))
                        }
                        block["heading_path"] = get_heading_path(stack)
                        stack[-1][1]["children"].append(block)
                # Extract text
                text_content = ''.join(c.content for c in inline_token.children if c.type == "text").strip()
                if text_content:
                    block = {
                        "type": "paragraph",
                        "text": text_content,
                        "element_id": generate_element_id({"text": text_content}, "paragraph", heading_path=get_heading_path(stack))
                    }
                    block["heading_path"] = get_heading_path(stack)
                    stack[-1][1]["children"].append(block)
            i += 3

        elif token.type == "inline" and token.children:
            for child in token.children:
                if child.type == "image":
                    block = {
                        "type": "image",
                        "alt": child.attrs.get("alt", ""),
                        "src": child.attrs["src"],
                        "element_id": generate_element_id(child.attrs, "image", heading_path=get_heading_path(stack))
                    }
                    block["heading_path"] = get_heading_path(stack)
                    stack[-1][1]["children"].append(block)
            i += 1

        elif token.type == "fence":
            block = {
                "type": "code",
                "language": token.info.strip(),
                "text": token.content.strip(),
                "element_id": generate_element_id({"text": token.content}, "code", heading_path=get_heading_path(stack))
                }
            block["heading_path"] = get_heading_path(stack)
            stack[-1][1]["children"].append(block)
            i += 1

        elif token.type == "table_open":
            table_tokens = []
            while i < len(tokens) and tokens[i].type != "table_close":
                table_tokens.append(tokens[i])
                i += 1
            i += 1  # Skip table_close

            # Convert token sequence to markdown string
            table_md_lines = []
            row = []
            is_header = False

            for tok in table_tokens:
                if tok.type == "thead_open":
                    is_header = True
                elif tok.type == "thead_close":
                    is_header = False
                    table_md_lines.append("| " + " | ".join(row) + " |")
                    table_md_lines.append("| " + " | ".join(["---"] * len(row)) + " |")
                    row = []
                elif tok.type == "tr_open":
                    row = []
                elif tok.type == "tr_close":
                    if not is_header:
                        table_md_lines.append("| " + " | ".join(row) + " |")
                elif tok.type == "inline":
                    row.append(tok.content.strip())

            table_md = "\n".join(table_md_lines)

            if table_md.strip():
                block = {
                    "type": "table",
                    "text": table_md,
                    "element_id": generate_element_id({"text": table_md}, "table", heading_path=get_heading_path(stack)),
                    "heading_path": get_heading_path(stack)
                }
                stack[-1][1]["children"].append(block)


        else:
            i += 1

    return root["children"]

def block_to_markdown(block):
    if block["type"] == "heading":
        return "#" * block["level"] + " " + block["text"]
    elif block["type"] == "paragraph":
        return block["text"]
    elif block["type"] == "image":
        return f'![{block.get("alt", "")}]({block["src"]})'
    elif block["type"] == "code":
        return f'```{block["language"]}\n{block["text"]}\n```'
    elif block["type"] == "table":
        return block["text"]
    return ""

def fallback_semantic_split(text, tokenizer, max_tokens):
    try:
        import semchunk
        sem_chunker = semchunk.chunkerify(tokenizer, chunk_size=max_tokens)
        return sem_chunker.chunk(text)
    except ImportError:
        print("⚠️ 'semchunk' not installed. Falling back to naive split.")
        return semantic_split_spacy(text, max_tokens, tokenizer)

def chunk_markdown(md_text: str, max_tokens: int = 2000, tokenizer_name: str = "gpt2", debug=False, debug_dir=Path("debug")) -> List[dict]:
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)

    chunks = []
    current_chunk = []
    current_tokens = 0

    def count_tokens(text: str) -> int:
        return len(tokenizer.encode(text))

    def is_atomic(block: dict) -> bool:
        return block["type"] in {"code", "table", "image"}

    def flatten_blocks_with_paths(tree_blocks):
        flat = []
        def walk(blocks, heading_path):
            for block in blocks:
                if block["type"] == "heading":
                    new_path = heading_path[:] + [block["text"]]
                    block["heading_path"] = new_path
                    flat.append(block)
                    walk(block.get("children", []), new_path)
                else:
                    block["heading_path"] = heading_path[:]
                    flat.append(block)
        walk(tree_blocks, [])
        return flat

    def enrich_block(block: dict) -> dict:
        b = dict(block)
        b["markdown"] = block_to_markdown(block)
        b["token_count"] = count_tokens(b["markdown"])
        b["is_atomic"] = is_atomic(block)
        return b

    def emit_chunk(enriched_blocks: list) -> dict:
        return {
            "blocks": enriched_blocks,
            "metadata": {
                "token_count": sum(b["token_count"] for b in enriched_blocks),
            },
        }

    tree_blocks = parse_markdown_as_tree(md_text)
    blocks = flatten_blocks_with_paths(tree_blocks)

    for block in blocks:
        enriched = enrich_block(block)

        # Oversized atomic → emit alone
        if enriched["is_atomic"] and enriched["token_count"] > max_tokens:
            chunks.append({
                "blocks": [enriched],
                "metadata": {
                    "token_count": enriched["token_count"],
                    "is_oversized": True,
                    "type": block["type"],
                    "reason": f"{block['type']}_too_large",
                }
            })
            continue

        # Oversized paragraph → semantic split while preserving original heading_path
        if block["type"] == "paragraph" and enriched["token_count"] > max_tokens:
            sub_chunks = fallback_semantic_split(enriched["markdown"], tokenizer, max_tokens)
            for sub in sub_chunks:
                sub_md = sub.strip()
                chunks.append({
                    "blocks": [{
                        "type": "paragraph",
                        "text": sub_md,
                        "markdown": sub_md,
                        "heading_path": enriched["heading_path"],
                        "token_count": count_tokens(sub_md),
                        "is_atomic": False,
                        "element_id": generate_element_id({"text": sub_md}, "paragraph", heading_path=enriched["heading_path"])
                    }],
                    "metadata": {
                        "token_count": count_tokens(sub_md),
                        "type": "paragraph"
                    }
                })
            continue

        # Start a new chunk if this one would overflow
        if current_tokens + enriched["token_count"] > max_tokens:
            if current_chunk:
                chunks.append(emit_chunk(current_chunk))

                # Token overlap (~200) — skip atomic blocks for overlap
                CHUNK_OVERLAP_TOKENS = 200
                rewind_tokens = 0
                overlap_chunk = []
                for b in reversed(current_chunk):
                    if b["is_atomic"]:
                        continue
                    rewind_tokens += b["token_count"]
                    overlap_chunk.insert(0, b)
                    if rewind_tokens >= CHUNK_OVERLAP_TOKENS:
                        break

                current_chunk = overlap_chunk
                current_tokens = rewind_tokens
            else:
                current_chunk = []
                current_tokens = 0

        current_chunk.append(enriched)
        current_tokens += enriched["token_count"]

    if current_chunk:
        chunks.append(emit_chunk(current_chunk))

    if debug and debug_dir:
        os.makedirs(debug_dir, exist_ok=True)
        from collections import Counter
        block_types = Counter()
        for chunk in chunks:
            for block in chunk["blocks"]:
                block_types[block["type"]] += 1

        print(f"🖼️ Images: {block_types['image']}")
        print(f"📊 Tables: {block_types['table']}")
        print(f"📄 Paragraphs: {block_types['paragraph']}")
        print(f"💻 Code blocks: {block_types['code']}")

        grouped_blocks = {"paragraph": [], "image": [], "table": [], "code": []}
        for chunk in chunks:
            for block in chunk["blocks"]:
                btype = block["type"]
                if btype in grouped_blocks:
                    grouped_blocks[btype].append(block)

        for btype, blks in grouped_blocks.items():
            file_path = os.path.join(debug_dir, f"{btype}s.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(blks, f, indent=2, ensure_ascii=False)

        def clean_block(b):
            return {k: v for k, v in b.items() if k != "children"}

        for c in chunks:
            c["blocks"] = [clean_block(b) for b in c["blocks"]]

        all_chunks_path = os.path.join(debug_dir, "chunks.json")
        with open(all_chunks_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)

    return chunks
