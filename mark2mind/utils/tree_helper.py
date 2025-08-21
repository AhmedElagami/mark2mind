import hashlib
from datetime import datetime
from slugify import slugify
from rich.tree import Tree as RichTree
from typing import Dict, List, Optional, Tuple

def _compute_node_id(path_titles: List[str], sibling_index: int) -> str:
    path_str = " / ".join(t or "untitled" for t in path_titles)
    slug = slugify(path_str) or "untitled"
    seed = f"{path_str}|depth={len(path_titles)-1}|sib={sibling_index}"
    h = hashlib.md5(seed.encode("utf-8")).hexdigest()[:8]
    return f"{slug}_{h}"

def assign_node_ids(node: Dict, path: Optional[List[str]] = None) -> None:
    path = (path or []) + [node.get("title", "")]
    if "node_id" not in node:
        node["node_id"] = _compute_node_id(path, sibling_index=0)
    children = node.get("children", []) or []
    for idx, child in enumerate(children):
        child_path = path + [child.get("title", "")]
        child["node_id"] = _compute_node_id(child_path, sibling_index=idx)
        assign_node_ids(child, path=path)

def insert_content_refs_into_tree(tree: Dict, mapped_content: List[Dict]) -> None:
    """
    Insert content refs into nodes. Supports:
      - paragraph/code/table/image: stored as markdown + element_caption
      - qa: stored as {type:'qa', q:'...', a:'...'}

    Each ref also includes:
      - ``markdown``: content (for QA this is ``## Q\nA``)
      - ``hash``: ``sha256:<hex>`` of ``markdown``
      - ``created_at``: ISO-8601 UTC timestamp
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

        rtype = (item.get("type") or "").lower()
        created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        if rtype == "qa":
            q = item.get("q") or ""
            a = item.get("a") or ""
            markdown = f"## {q}\n{a}"
            h = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
            target.setdefault("content_refs", []).append(
                {
                    "element_id": item.get("element_id"),
                    "type": "qa",
                    "q": q,
                    "a": a,
                    "markdown": markdown,
                    "hash": f"sha256:{h}",
                    "created_at": created_at,
                }
            )
        else:
            markdown = item.get("markdown", "") or ""
            h = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
            target.setdefault("content_refs", []).append(
                {
                    "element_id": item.get("element_id"),
                    "type": rtype,
                    "element_caption": item.get("element_caption"),
                    "markdown": markdown,
                    "hash": f"sha256:{h}",
                    "created_at": created_at,
                }
            )

def add_order_and_fingerprint(node: Dict, path_titles: Optional[List[str]] = None, order: int = 0) -> None:
    """Recursively add ``order`` and ``origin.fingerprint`` to each node."""
    path_titles = path_titles or []
    node["order"] = order

    # primary content hash from first content_ref markdown (if any)
    content_refs = node.get("content_refs") or []
    primary_md = content_refs[0].get("markdown", "") if content_refs else ""
    primary_hash = hashlib.sha1(primary_md.encode("utf-8")).hexdigest()
    path_joined = " / ".join(path_titles)
    base = f"{(node.get('title') or '').lower()}|{path_joined}|{primary_hash}"
    fingerprint = hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]
    node["origin"] = {"fingerprint": fingerprint}

    for idx, child in enumerate(node.get("children", []) or []):
        add_order_and_fingerprint(child, path_titles + [node.get("title", "")], idx)

def render_tree(node: Dict, rich_tree: Optional[RichTree] = None):
    label = f"[bold]{node['title']}[/]"
    if "node_id" in node:
        label += f" ([dim]{node['node_id']}[/])"
    current = rich_tree.add(label) if rich_tree else RichTree(label)
    for child in node.get("children", []):
        render_tree(child, current)
    return current

def normalize_tree(node: dict) -> dict:
    if not isinstance(node, dict):
        return {"title": "Untitled", "children": []}
    if "title" in node and "children" in node:
        return {
            "title": node.get("title") or "Untitled",
            "children": [normalize_tree(c) for c in node.get("children", [])]
        }
    if "root" in node or "nodes" in node:
        return {
            "title": node.get("root") or node.get("title") or "Untitled",
            "children": [normalize_tree(c) for c in node.get("nodes", [])]
        }
    title = node.get("title") or node.get("root") or "Untitled"
    kids = node.get("children") or node.get("nodes") or []
    return {"title": title, "children": [normalize_tree(c) for c in kids]}
