from pathlib import Path
from typing import List, Dict, Any
import html

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
                lines.append(f"\n{question_prefix} Q{question_counter}. {qa['question'].strip()}")
                answer = (qa.get("answer") or "").strip()

                # Preserve markdown blocks verbatim (code/table/image) vs plain text
                if answer.startswith("```") or answer.startswith("|") or answer.startswith("![](") or answer.startswith("!["):
                    lines.append(answer)
                else:
                    lines.append(f"A: {answer}")

                lines.append("")  # spacer
                question_counter += 1

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ Exported {question_counter - 1} questions to {output_path}")

def _esc(s: str) -> str:
    # minimal escaping for list text
    return (s or "").replace("\n", " ").strip()

def _render_content_ref(ref: Dict[str, Any]) -> List[str]:
    """
    Produce ONLY the original markdown (no captions) in Markmap-friendly form.

    Rules:
      - Paragraphs: a bullet "- <first line>", extra lines as indented content.
      - Code/Table/Image: an empty bullet "-" followed by the raw block lines.
    """
    body = (ref.get("markdown") or "").strip()
    if not body:
        return []

    is_structural = body.startswith("```") or body.startswith("|") or body.startswith("![")
    lines: List[str] = []

    if is_structural:
        # Bullet line without label; raw block lines follow.
        lines.append("-")
        lines.extend(body.splitlines())
    else:
        # Paragraph text on the bullet; extra lines below.
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

