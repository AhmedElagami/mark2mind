import hashlib
from typing import Dict, List, Optional
from slugify import slugify
from rich.tree import Tree as RichTree


def assign_node_ids(node: Dict) -> None:
    """
    Recursively assign unique node IDs based on title.
    """
    title = node.get("title", "")
    base_slug = slugify(title) if title else "untitled"
    hash_suffix = hashlib.md5(title.encode("utf-8")).hexdigest()[:4]
    node["node_id"] = f"{base_slug}_{hash_suffix}"
    for child in node.get("children", []):
        assign_node_ids(child)


def insert_content_refs_into_tree(tree: Dict, mapped_content: List[Dict]) -> None:
    """
    Insert content reference metadata into target nodes within the tree.
    """
    def find_node(node: Dict, node_id: str) -> Optional[Dict]:
        if node.get("node_id") == node_id:
            return node
        for child in node.get("children", []):
            result = find_node(child, node_id)
            if result:
                return result
        return None

    for item in mapped_content:
        target = find_node(tree, item.get("target_node_id"))
        if target:
            target.setdefault("content_refs", []).append({
                "element_id": item["element_id"],
                "element_type": item["element_type"],
                "element_caption": item["element_caption"]
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
