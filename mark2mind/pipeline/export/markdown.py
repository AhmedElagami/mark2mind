from __future__ import annotations
from pathlib import Path

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
