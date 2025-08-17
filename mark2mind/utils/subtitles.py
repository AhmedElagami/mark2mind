from __future__ import annotations
import os, re
from typing import Iterable
from markdownify import markdownify as md


def natural_sort_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]


def clean_subtitle_content(content: str) -> str:
    content = content.replace('\ufeff', '')
    content = re.sub(r'^(WEBVTT.*\n+)', '', content, flags=re.IGNORECASE)
    ts = r'^\s*(\d+:)?\d{1,2}:\d{2}([.,]\d+)?\s*-->\s*(\d+:)?\d{1,2}:\d{2}([.,]\d+)?\s*$'
    content = re.sub(ts, '', content, flags=re.MULTILINE)
    content = re.sub(r'^\d+\s*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'\n\s*\n+', '\n', content)
    return content.strip()


def _collect_files(base_dir: str, enable_html: bool) -> list[str]:
    all_files: list[str] = []
    for root, _, files in os.walk(base_dir):
        for f in files:
            fl = f.lower()
            if fl.endswith(('.srt', '.vtt')) or (enable_html and fl.endswith('.html')):
                all_files.append(os.path.abspath(os.path.join(root, f)))
    all_files.sort(key=natural_sort_key)
    return all_files


def list_subtitle_files(base_dir: str, output_file: str = "file_list.txt", enable_html: bool = False) -> str:
    """
    Writes absolute file list to output_file (path provided by caller).
    WHY: Runner now resolves relative path under workspace.
    """
    files = _collect_files(base_dir, enable_html)
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write("\n".join(files))
    return output_file


def merge_from_list(file_list_path: str, output_md: str = "merged_subtitles.md", enable_html: bool = False) -> str:
    with open(file_list_path, 'r', encoding='utf-8') as f:
        files = [line.strip() for line in f if line.strip()]

    last_dir: str | None = None
    os.makedirs(os.path.dirname(output_md) or ".", exist_ok=True)

    with open(output_md, 'w', encoding='utf-8') as md_out:
        for filepath in files:
            if not os.path.exists(filepath):
                print(f"Warning: {filepath} does not exist, skipping.")
                continue
            if not enable_html and filepath.lower().endswith('.html'):
                print(f"Skipping HTML file {filepath} (HTML not enabled).")
                continue
            dir_name = os.path.basename(os.path.dirname(filepath))
            if dir_name != last_dir:
                md_out.write(f"# {dir_name}\n\n")
                last_dir = dir_name

            md_out.write(f"## {os.path.basename(filepath)}\n\n")
            if filepath.lower().endswith(('.srt', '.vtt')):
                with open(filepath, 'r', encoding='utf-8') as f_sub:
                    cleaned = clean_subtitle_content(f_sub.read())
                    md_out.write(cleaned + "\n\n")
            else:
                with open(filepath, 'r', encoding='utf-8') as f_html:
                    markdown_content = md(f_html.read(), heading_style="ATX")
                    md_out.write(markdown_content + "\n\n")

    return output_md
