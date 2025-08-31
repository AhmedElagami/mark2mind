# mark2mind

**Semantic mindmap & Q\&A generator for Markdown and subtitles.**
Built with [LangChain](https://www.langchain.com/) + LLMs.

Generate:

* 📌 **Mindmaps** (basic or detailed)
* ❓ **Q\&A study guides**
* 📑 **Structured outlines & bullets**
* 🧹 **Reformatted or cleaned Markdown for mapping**
* 🎬 **Subtitle collection & merging**

---

## 🚀 Installation

```bash
# Clone and install in editable mode
git clone https://github.com/your-repo/mark2mind.git
cd mark2mind
pip install -e .
```

Requirements:

* Python ≥ 3.8
* API key for your chosen LLM provider (default: DeepSeek).

  ```bash
  export DEEPSEEK_API_KEY="sk-..."
  ```

---

## 🏃 Quick Start

```bash
# Generate a detailed mindmap from a Markdown file
mark2mind --recipe detailed_mindmap_from_markdown --input notes/intro.md
```

Outputs will be created under:

```
output/<run_name>/
  ├─ mindmap.json          # JSON structure
  ├─ mindmap.markmap.md    # Interactive Markmap-compatible Markdown
  ├─ qa.md                 # (if QA run) nested questions & answers
  ├─ bullets.md            # (if outline run) bullet-point summary
```

Debug artifacts live under:

```
debug/<run_name>/...
```

---

## 📦 Using Recipes

Recipes are **prebuilt TOML configs** that define complete workflows.
List them with:

```bash
mark2mind --list-recipes
```

### Built-in Recipes

| Recipe                       | Preset            | What it Does                                                       |
|------------------------------|-------------------|--------------------------------------------------------------------|
| `mindmap_from_markdown`      | `mindmap`         | Chunk → Tree → Cluster → Merge → Refine → Mindmap                  |
| `detailed_mindmap_from_markdown` | `detailed_mindmap` | Same as above + `map` stage (attaches content/code/tables/images to nodes) |
| `mindmap_from_qa`            | `mindmap_from_qa` | Parse Q&A Markdown and build a mindmap with Q&A attached to nodes  |
| `map_qa_onto_markmap`        | `map_qa_onto_markmap` | Map Q&A onto an existing Markmap                                   |
| `qa_from_markdown`           | `qa`              | Chunk text, then generate Q&A per block                            |
| `outline_markdown`           | `bullets`         | Bullet-point outline of Markdown                                   |
| `reformat_markdown`          | `reformat`        | Rewrites Markdown into cleaner prose                               |
| `focus_markdown`             | `clean_for_map`   | Simplifies Markdown for easier mapping                             |
| `list_notes_in_dir`          | `subs_list`       | Collect subtitles (.srt, .vtt, .html) into a manifest              |
| `merge_notes_from_manifest`  | `subs_merge`      | Merge subtitle manifest into a Markdown transcript                 |

Aliases also exist, e.g. `list_subtitles_in_dir → list_notes_in_dir`.

---

## ⚙️ Pipeline Stages

Workflows are defined by **steps**. A `preset` is just a shortcut for a step list.
You can override stages manually with `--steps`.

### Available Stages

| Stage           | Purpose                                                            |
| --------------- | ------------------------------------------------------------------ |
| `chunk`         | Split Markdown into semantic chunks                                |
| `tree`          | Generate hierarchical tree per chunk                               |
| `cluster`       | Cluster chunk trees (semantic grouping)                            |
| `merge`         | Merge clustered trees                                              |
| `refine`        | Refine & assign stable IDs to tree                                 |
| `map`           | Map original content (code, tables, images, paragraphs) into nodes |
| `qa`            | Generate questions & answers per block                             |
| `qa_parse`     | Parse Q&A markdown into blocks for mapping                         |
| `bullets`       | Turn chunks into bullet lists                                      |
| `reformat`      | Reformat raw Markdown                                              |
| `clean_for_map` | Simplify Markdown for mapping                                      |
| `subs_list`     | Scan a directory for subtitle files                                |
| `subs_merge`    | Merge subtitles into one Markdown file                             |

### Example: Run a custom step sequence

```bash
mark2mind --config config.toml --steps chunk,qa
```

This chunks text and generates Q\&A only.

---

## 📁 Config File (`config.toml`)

The config lets you fine-tune everything. Example:

```toml
[pipeline]
preset = "detailed_mindmap"   # or steps=["chunk","tree","cluster","merge","refine","map"]

[io]
input = "notes/intro.md"      # file or directory
output_dir = "output"
debug_dir  = "debug"

[chunk]
tokenizer_name = "gpt2"
max_tokens = 1024
overlap_tokens = 0

[llm]
provider = "deepseek"
model = "deepseek-chat"
api_key_env = "DEEPSEEK_API_KEY"
temperature = 0.2
max_tokens = 8000

[runtime]
debug = true
use_debug_io = true
executor_max_workers = 24
min_delay_sec = 1
```

---

## 👩‍💻 Developer Notes

* **Entry point**: `mark2mind.main:main` (CLI)
* **Pipeline runner**: `mark2mind.pipeline.runner.StepRunner` orchestrates stages.
* **Recipes** live in `mark2mind/recipes/*.toml`, copied to `~/.mark2mind/recipes/` at first run.
* **Prompts** are in `mark2mind/prompts/**`, override via `config.toml → [prompts.files]`.
* **Artifacts** are managed by `ArtifactStore`. Debug files (JSON) are saved automatically.
* **Tracing**: enable with `--enable-tracing` to get per-step LangChain trace logs in `debug/<run>/traces/`.
* **Extending**: Add new stages under `mark2mind/pipeline/stages/` and wire them in `StepRunner`.

---

## 🔍 Examples

### Generate Q\&A guide from Markdown

```bash
mark2mind --recipe qa_from_markdown --input notes/kubernetes.md
```

→ Output: `output/kubernetes/qa.md`

---

### Build a mindmap from Q&A Markdown

```bash
mark2mind --recipe mindmap_from_qa --input notes/qa.md
```

→ Output: `output/qa/mindmap.markmap.md`

---

### Map Q&A onto an existing Markmap

```bash
mark2mind --recipe map_qa_onto_markmap --input-markmap mindmap.md --input-qa qa.md --run-name MyTopic
```

→ Output: `output/MyTopic/MyTopic.mindmap.json`

---

### Convert a folder of subtitles into Markdown

```bash
# Step 1: collect all subtitles into a manifest
mark2mind --recipe list_notes_in_dir --input data/subtitles_course

# Step 2: merge them into a Markdown transcript
mark2mind --recipe merge_notes_from_manifest --input data/subtitles_course
```

→ Output: `output/subtitles_course/subtitles_merged.md`

---

### Custom workflow with config file

```bash
mark2mind --config custom_config.toml
```

---

## 📜 License

MIT (c) Ahmed Elagami
