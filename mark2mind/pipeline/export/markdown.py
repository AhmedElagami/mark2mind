from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional
from slugify import slugify

class MarkdownExporter:
    def export_markmap(self, final_tree: dict, out_path: Path):
        try:
            from mark2mind.utils.exporters import export_tree_as_markmap_md
            out_path.parent.mkdir(parents=True, exist_ok=True)
            export_tree_as_markmap_md(final_tree, str(out_path))
        except Exception as e:
            # best-effort; swallow errors but you can log upstream
            pass

    def export_qa(self, chunks: list, out_path: Path):
        try:
            from mark2mind.utils.exporters import export_qa_nested_headers
            out_path.parent.mkdir(parents=True, exist_ok=True)
            export_qa_nested_headers(chunks, str(out_path))
        except Exception:
            pass

    def export_bullets(self, bullets_outputs: list, out_path: Path): 
            """
            bullets_outputs: [{chunk_index:int, markdown:str, ...}, ...]
            """
            out_path.parent.mkdir(parents=True, exist_ok=True)
            body = "\n\n".join((item.get("markdown") or "").rstrip() for item in bullets_outputs)
            out_path.write_text(body + ("\n" if body and not body.endswith("\n") else ""), encoding="utf-8")

    def export_markmap_with_node_pages(
        self,
        tree: Dict[str, Any],
        out_md_path: Path,
        pages_dir: Path,
        link_folder_name: str,
        progress: Optional[Any] = None,
    ):
        """
        - Writes <file_name>.markmap.md with links like: [Node](<file_name>/<node>.md)
        - For every node that has content_refs, writes a page at: <file_name>/<node>.md
        """
        from mark2mind.utils.exporters import export_tree_as_markmap_md_with_links_and_pages
        out_md_path.parent.mkdir(parents=True, exist_ok=True)
        pages_dir.mkdir(parents=True, exist_ok=True)
        export_tree_as_markmap_md_with_links_and_pages(
            tree=tree,
            markmap_md_path=str(out_md_path),
            pages_dir=str(pages_dir),
            link_folder_name=link_folder_name,
            progress=progress,
        )
