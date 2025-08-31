from __future__ import annotations
from pathlib import Path
import re
from typing import Dict, List, Tuple

from ..core.context import RunContext
from ..core.artifacts import ArtifactStore
from ..core.progress import ProgressReporter
from mark2mind.utils.tree_helper import assign_node_ids


class ImportMarkmapStage:
    """Load an existing Markmap markdown file into ctx.final_tree."""

    ARTIFACT = "import_markmap_tree.json"

    def _parse(self, text: str) -> Dict:
        lines = text.splitlines()
        root: Dict | None = None
        stack: List[Tuple[int, Dict]] = []  # (depth, node)
        heading_re = re.compile(r"^(#{1,6})\s+(.*)")
        bullet_re = re.compile(r"^(?P<indent>\s*)-\s+(.*)")
        link_re = re.compile(r"\[(.+?)\]\(.*?\)")

        for line in lines:
            if not line.strip():
                continue
            h = heading_re.match(line)
            if h:
                level = len(h.group(1)) - 1  # depth 0 for '#'
                title = h.group(2).strip()
                mlink = link_re.fullmatch(title)
                if mlink:
                    title = mlink.group(1)
                node = {"title": title, "children": []}
                if level == 0 or not stack:
                    root = node
                    stack = [(0, root)]
                else:
                    while stack and stack[-1][0] >= level:
                        stack.pop()
                    parent = stack[-1][1] if stack else root
                    (parent.setdefault("children", [])).append(node)
                    stack.append((level, node))
                continue
            b = bullet_re.match(line)
            if b:
                indent = len(b.group("indent"))
                depth = indent // 2
                title = b.group(2).strip()
                mlink = link_re.fullmatch(title)
                if mlink:
                    title = mlink.group(1)
                node = {"title": title, "children": []}
                if not stack:
                    root = node
                    stack = [(depth, node)]
                else:
                    while stack and stack[-1][0] >= depth:
                        stack.pop()
                    parent = stack[-1][1] if stack else root
                    (parent.setdefault("children", [])).append(node)
                    stack.append((depth, node))
        if not root:
            raise ValueError("Invalid Markmap: missing root heading or bullet")
        return root

    def run(
        self,
        ctx: RunContext,
        store: ArtifactStore,
        progress: ProgressReporter,
        *,
        markmap_path: str | None,
        use_debug_io: bool,
    ) -> RunContext:
        if not markmap_path:
            raise FileNotFoundError("Missing markmap input. Provide --input-markmap")
        path = Path(markmap_path)
        if not path.exists():
            raise FileNotFoundError(f"Markmap file not found: {markmap_path}")

        if use_debug_io:
            loaded = store.load_debug(self.ARTIFACT)
            if loaded is not None:
                ctx.final_tree = loaded
                return ctx

        task = progress.start("Importing Markmap", total=1)
        text = path.read_text(encoding="utf-8")
        tree = self._parse(text)
        assign_node_ids(tree)
        ctx.final_tree = tree
        store.save_debug(self.ARTIFACT, tree)
        progress.advance(task)
        progress.finish(task)
        return ctx
