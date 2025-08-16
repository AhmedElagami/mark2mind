from pathlib import Path

PROMPT_REGISTRY = {
    "chunk_tree": "prompts/mindmap/mindmap_generator.txt",
    "merge_tree": "prompts/mindmap/mindmap_merger.txt",
    "refine_tree": "prompts/mindmap/mindmap_refiner.txt",
    "map_content": "prompts/mindmap/content_mapper.txt",
    "qa_generate": "prompts/qa/generate_questions.txt",
    "qa_answer": "prompts/qa/answer_questions.txt",
    "format_bullets": "prompts/format/format_bullets.txt",
    "reformat_text": "prompts/format/reformat_text.txt",
    "clean_for_map": "prompts/format/clean_for_map.txt"
}

def load_prompt(key: str) -> str:
    if key not in PROMPT_REGISTRY:
        raise ValueError(f"No prompt registered for key: {key}")
    path = Path(PROMPT_REGISTRY[key])
    return path.read_text(encoding="utf-8")
