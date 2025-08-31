from pathlib import Path
from typing import List, Dict, Any
import html
from slugify import slugify

import re

def to_camel_nospace(s: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9]+", (s or "Untitled"))
    if not tokens:
        return "Untitled"
    # UpperCamelCase: "my cool node" -> "MyCoolNode"
    return "".join(t.capitalize() for t in tokens)


def export_qa_nested_headers(chunks: List[Dict[str, Any]], output_path: str) -> None:
    lines = []
    question_counter = 1
    rendered_heading_keys: set[tuple] = set()


    def render_heading_path(heading_path):
        # track rendered path segments as tuples, so identical segment names
        # under different parents are still printed correctly
        md_lines = []
        for level in range(1, len(heading_path) + 1):
            prefix_tuple = tuple(heading_path[:level])
            if prefix_tuple not in rendered_heading_keys:
                md_lines.append(f"{'#' * level} {heading_path[level-1]}")
                rendered_heading_keys.add(prefix_tuple)
        return md_lines


    for chunk in chunks:
        for block in chunk.get("blocks", []):
            qa_pairs = block.get("qa_pairs", [])
            if not qa_pairs:
                continue

            heading_path = block.get("heading_path", [])
            lines.extend(render_heading_path(heading_path))

            question_level = len(heading_path) + 1
            question_prefix = "#" * question_level

            for qa in qa_pairs:
                # lines.append(f"\n{question_prefix} Q{question_counter}. {qa['question'].strip()}")
                lines.append(f"\n{question_prefix} {qa['question'].strip()}")
                answer = (qa.get("answer") or "").strip()

                # Preserve markdown blocks verbatim (code/table/image) vs plain text
                if answer.startswith("```") or answer.startswith("|") or answer.startswith("![](") or answer.startswith("!["):
                    lines.append(answer)
                else:
                    # lines.append(f"A: {answer}")
                    lines.append(f"{answer}")

                lines.append("")  # spacer
                question_counter += 1

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ Exported {question_counter - 1} questions to {output_path}")

def _esc(s: str) -> str:
    # minimal escaping for list text
    return (s or "").replace("\n", " ").strip()

def _render_content_ref(ref: Dict[str, Any]) -> List[str]:
    """
    Render a content_ref for Markmap.

    Rules:
      - Paragraph: bullet text is the paragraph's first line (as before).
      - Image/Table/Code: bullet shows a caption (element_caption/alt/fallback),
        and the raw block (image markdown, table, or code fence) is nested under it.
    """
    body = (ref.get("markdown") or "").strip()
    rtype = (ref.get("type") or "").lower()
    caption = (ref.get("element_caption") or "").strip()

    # Helper to keep a readable caption
    def caption_or_fallback(default: str) -> str:
        return caption or default

    lines: List[str] = []

    if rtype == "paragraph":
        if not body:
            return []
        parts = body.splitlines()
        lines.append(f"- {parts[0]}")     # bullet line
        lines.extend(parts[1:])           # any extra lines as nested text
        return lines

    if rtype == "image":
        label = caption_or_fallback("Image")
        # bullet with caption; raw image markdown on the next lines
        lines.append(f"- 🖼 {label}")
        if body:
            lines.extend(body.splitlines())
        return lines

    if rtype == "code":
        label = caption_or_fallback("Code")
        lines.append(f"- 🧩 {label}")
        if body:
            lines.extend(body.splitlines())  # should already be a fenced block
        return lines

    if rtype == "table":
        label = caption_or_fallback("Table")
        lines.append(f"- 📊 {label}")
        if body:
            lines.extend(body.splitlines())  # pipe table lines
        return lines

    # Fallback: treat unknown like a paragraph
    if body:
        parts = body.splitlines()
        lines.append(f"- {parts[0]}")
        lines.extend(parts[1:])
    return lines



def _walk_node(node: Dict[str, Any], depth: int, out: List[str]) -> None:
    """
    Walk the tree and emit strict Markmap-compatible markdown:
      # Title
      - Child
        - <paragraph line>
        -
          ```lang
          code...
          ```
    """
    indent = "  " * depth
    title = _esc(node.get("title") or "Untitled")

    if depth == 0:
        out.append(f"# {title}")
    else:
        out.append(f"{indent}- {title}")

    # content refs under this node
    refs = node.get("content_refs") or []
    for ref in refs:
        rendered = _render_content_ref(ref)
        if not rendered:
            continue

        # First line: either "- <paragraph-first-line>" or "-" for structural blocks
        out.append(f"{indent}  {rendered[0]}")

        # Subsequent lines: indent by 4 spaces so Markmap nests them under the same bullet
        for md_line in rendered[1:]:
            out.append(f"{indent}    {md_line}")

    # children
    for child in node.get("children", []) or []:
        _walk_node(child, depth + 1, out)

def export_tree_as_markmap_md(tree: Dict[str, Any], output_path: str) -> None:
    """
    Render a normalized tree (after assign_node_ids + map_content) to Markdown that Markmap can preview.
    Structure:
      # Root
      - Child A
        - Grandchild A1
          - [paragraph] ...
          - [code] Caption
            ```lang
            ...
            ```
    NOTE: By default we only include captions for content refs, because the current pipeline
          doesn't store raw markdown on the refs. If you want full elements, see below.
    """
    lines: List[str] = []
    _walk_node(tree, depth=0, out=lines)
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"✅ Markmap Markdown saved to: {output_path}")

def _node_slug(node: Dict[str, Any]) -> str:
    title = _esc(node.get("title") or "Untitled")
    return to_camel_nospace(title)


def _render_node_page(node: Dict[str, Any]) -> str:
    title = _esc(node.get("title") or "Untitled")
    refs = node.get("content_refs") or []
    lines: List[str] = []
    # frontmatter passthrough: if first ref begins with YAML block, put it at top
    if refs:
        md0 = (refs[0].get("markdown") or "")
        if md0.lstrip().startswith("---\n"):
            # extract YAML block
            fm_end = md0.find("\n---", 4)
            if fm_end != -1:
                fm_block = md0[:fm_end+4].strip()
                rest = md0[fm_end+4:].lstrip("\n")
                lines.append(fm_block)
                lines.append("")  # spacer
                # replace the first ref body with the remainder (without YAML header)
                refs[0]["markdown"] = rest
    lines.append(f"# {title}")
    lines.append("")
    if not refs:
        lines.append("> No content refs.")
        return "\n".join(lines) + "\n"
    lines.append("## Content")
    lines.append("")
    for ref in refs:
        rtype = (ref.get("type") or "").lower()
        cap = ref.get("element_caption") or ""
        if rtype == "qa":
            q = (ref.get("q") or "").strip()
            a = (ref.get("a") or "").strip()
            lines.append(f"### ❓ {q}")
            if a.startswith("```") or a.startswith("|") or a.startswith("!"):
                lines.append(a)
            else:
                lines.append(a)
            lines.append("")
        else:
            if cap:
                lines.append(f"### {cap}")
            md = (ref.get("markdown") or "").strip()
            if md:
                lines.append(md)
            lines.append("")
    return "\n".join(lines) + "\n"

def export_tree_as_markmap_md_with_links_and_pages(
    tree: Dict[str, Any],
    markmap_md_path: str,
    pages_dir: str,
    link_folder_name: str,
):
    """
    Produces:
      - markmap MD where nodes with content are links: [Title](<link_folder_name>/<node>.md)
      - for those nodes, writes <pages_dir>/<node>.md with their content_refs rendered
    """
    lines: List[str] = []
    pages_root = Path(pages_dir)
    pages_root.mkdir(parents=True, exist_ok=True)

    def walk(node: Dict[str, Any], depth: int):
        indent = "  " * depth
        title = _esc(node.get("title") or "Untitled")
        has_refs = bool(node.get("content_refs"))
        if depth == 0:
            # top-level heading (Markmap root)
            if has_refs:
                slug = _node_slug(node)
                rel = f"{link_folder_name}/{slug}.md"
                lines.append(f"# [{title}]({rel})")
            else:
                lines.append(f"# {title}")
        else:
            if has_refs:
                slug = _node_slug(node)
                rel = f"{link_folder_name}/{slug}.md"
                lines.append(f"{indent}- [{title}]({rel})")
            else:
                lines.append(f"{indent}- {title}")

        # If this node has refs, emit its page
        if has_refs:
            page_path = pages_root / f"{_node_slug(node)}.md"
            page_path.write_text(_render_node_page(node), encoding="utf-8")

        for child in node.get("children", []) or []:
            walk(child, depth + 1)

    walk(tree, 0)
    Path(markmap_md_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"✅ Markmap (linked) saved to: {markmap_md_path}")
def normalize_newlines(s: str) -> str:
    """
    Normalize newlines and strip BOM if present.
    - Converts \r\n and \r to \n
    - Removes leading UTF-8 BOM (\\ufeff)
    - Strips trailing whitespace
    """
    if s is None:
        return ""
    return s.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")

from markdown_it import MarkdownIt

def unwrap_if_single_fence_md(text: str) -> str:
    s = normalize_newlines(text).strip()
    md = MarkdownIt("gfm-like")
    tokens = [t for t in md.parse(s) if t.type != "inline"]
    if len(tokens) == 1 and tokens[0].type in ("fence", "code_block"):
        return tokens[0].content.rstrip("\n")
    return s
