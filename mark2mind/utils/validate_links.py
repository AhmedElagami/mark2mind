import re
from pathlib import Path


def collect_wikilinks(text: str) -> set[str]:
    return {m.group(1).split("|", 1)[0].split("/", 1)[-1] for m in re.finditer(r"\[\[([^\]]+)\]\]", text)}


def validate_pages(pages_dir: Path) -> list[str]:
    files = list(pages_dir.glob("*.md"))
    slugs = {p.stem for p in files}
    missing = []
    for p in files:
        s = collect_wikilinks(p.read_text(encoding="utf-8"))
        for w in s:
            if w not in slugs:
                missing.append(f"{p.name}: [[{w}]] not found")
    return missing
