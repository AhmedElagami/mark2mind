import hashlib
from slugify import slugify
from rich.tree import Tree as RichTree
from typing import Dict, List, Optional, Tuple

def _compute_node_id(path_titles: List[str], sibling_index: int) -> str:
    """
    Compute a stable, collision-resistant node_id from:
      - the full path of titles (root → node)
      - the node's sibling index at its depth
    """
    path_str = " / ".join(t or "untitled" for t in path_titles)
    # slug for readability, hash for uniqueness
    slug = slugify(path_str) or "untitled"
    seed = f"{path_str}|depth={len(path_titles)-1}|sib={sibling_index}"
    h = hashlib.md5(seed.encode("utf-8")).hexdigest()[:8]
    return f"{slug}_{h}"

def assign_node_ids(node: Dict, path: Optional[List[str]] = None) -> None:
    """
    Recursively assign unique, stable node IDs based on full path and order.
    This prevents collisions when titles repeat in different branches.
    """
    path = (path or []) + [node.get("title", "")]
    # keep existing node_id if already set by parent enumeration
    if "node_id" not in node:
        node["node_id"] = _compute_node_id(path, sibling_index=0)

    children = node.get("children", []) or []
    for idx, child in enumerate(children):
        child_path = path + [child.get("title", "")]
        child["node_id"] = _compute_node_id(child_path, sibling_index=idx)
        assign_node_ids(child, path=path)  # don't recompute child ID inside





def insert_content_refs_into_tree(tree: Dict, mapped_content: List[Dict]) -> None:
    """
    Insert content references into the final tree INCLUDING the raw markdown,
    so the exporter can render actual content (not captions).
    """
    def find_node(node: Dict, node_id: str) -> Optional[Dict]:
        if node.get("node_id") == node_id:
            return node
        for child in node.get("children", []):
            found = find_node(child, node_id)
            if found:
                return found
        return None

    for item in mapped_content:
        target = find_node(tree, item.get("target_node_id"))
        if not target:
            continue
        target.setdefault("content_refs", []).append({
            "element_id": item.get("element_id"),
            "type": item.get("type"),
            # Keep caption for debugging/tracing, but the exporter will ignore it
            "element_caption": item.get("element_caption"),
            # ✅ store the raw markdown so it can be exported
            "markdown": item.get("markdown", "") or ""
        })

def render_tree(node: Dict, rich_tree: Optional[RichTree] = None):
    """
    Render a mindmap tree to a rich-style tree output for CLI.
    """
    label = f"[bold]{node['title']}[/]"
    if "node_id" in node:
        label += f" ([dim]{node['node_id']}[/])"
    current = rich_tree.add(label) if rich_tree else RichTree(label)
    for child in node.get("children", []):
        render_tree(child, current)
    return current

def normalize_tree(node: dict) -> dict:
    """
    Accepts either:
      - {"root": "...", "nodes": [...]}
      - {"title": "...", "children": [...]}
      - or slightly malformed variants
    Returns canonical {"title": str, "children": [ ... ]}.
    """
    if not isinstance(node, dict):
        return {"title": "Untitled", "children": []}

    # Already canonical
    if "title" in node and "children" in node:
        return {
            "title": node.get("title") or "Untitled",
            "children": [normalize_tree(c) for c in node.get("children", [])]
        }

    # "root"/"nodes" variant
    if "root" in node or "nodes" in node:
        return {
            "title": node.get("root") or node.get("title") or "Untitled",
            "children": [normalize_tree(c) for c in node.get("nodes", [])]
        }

    # Leaf fallback
    title = node.get("title") or node.get("root") or "Untitled"
    kids = node.get("children") or node.get("nodes") or []
    return {"title": title, "children": [normalize_tree(c) for c in kids]}

