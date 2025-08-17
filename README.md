# mark2mind

> Transform raw text or subtitles into **mindmaps**, **Q&A notes**, or **clean formatted markdown** using LLM pipelines.  
> Designed for both beginners (one-command presets) and advanced users (fine-grained pipeline control).

---

## 🚀 Overview

**mark2mind** is a command-line tool that helps you:

- Generate **mindmaps** from Markdown or subtitles.
- Create **Q&A summaries** of text documents.
- Merge and clean **subtitle collections**.
- Reformat or bullet text for clarity.

It runs as a pipeline of stages (chunking, tree building, clustering, merging, refining, mapping, etc.), powered by an LLM backend (DeepSeek or similar).

Outputs are automatically organized under:

```

output/\<run\_name>/

```

Debugging and tracing data are stored under:

```

debug/\<run\_name>/

````

---

## 📦 Installation

Requirements:

- Python **3.10+** (tested on 3.11/3.12).
- [Poetry](https://python-poetry.org/) or `pip` for dependency management.
- A supported LLM API key (e.g. `DEEPSEEK_API_KEY`).

Clone and install:

```bash
git clone https://github.com/yourname/mark2mind.git
cd mark2mind

# install dependencies
pip install -e .
````

Check installation:

```bash
python -m mark2mind --help
```

---

## 🏁 Quick Start (Beginner)

### 1. Minimal Config

Save as `config.toml`:

```toml
[io]
input = "examples/sample.md"   # file or directory
output_dir = "output"
debug_dir = "debug"

[pipeline]
preset = "mindmap"             # or qa | detailed_mindmap | subs_list | subs_merge

[llm]
provider = "deepseek"
model = "deepseek-chat"
api_key_env = "DEEPSEEK_API_KEY"
```

### 2. Run Presets

Each preset defines a ready-to-use pipeline:

#### Mindmap

```bash
python -m mark2mind --config config.toml --preset mindmap
```

Outputs:

* `output/<run_name>/mindmap.json`
* `output/<run_name>/mindmap.markmap.md`

#### Detailed Mindmap

```bash
python -m mark2mind --config config.toml --preset detailed_mindmap
```

Outputs: same as above, but with **extra content mapping**.

#### Q\&A

```bash
python -m mark2mind --config config.toml --preset qa
```

Outputs:

* `output/<run_name>/qa.md`

#### Subtitles (list files)

```bash
python -m mark2mind --config config.toml --preset subs_list
```

Outputs:

* `output/<run_name>/file_list.txt` (or custom manifest)

#### Subtitles (merge)

```bash
python -m mark2mind --config config.toml --preset subs_merge
```

Requires an existing manifest (from `subs_list`).
Outputs:

* `output/<run_name>/subtitles_merged.md`

---

## 🧾 What Recipes Are

* A **recipe** = a `config.toml` file pre-configured for a common task.
* Each recipe lives in a `recipes/` folder inside the package.
* Examples: `mindmap_from_markdown.toml`, `qa_from_markdown.toml`, `list_subtitles_in_dir.toml`.
* Users run them via:

  * Direct path:

    ```bash
    mark2mind --config recipes/mindmap_from_markdown.toml --input notes.md
    ```
  * Shortcut CLI (if you expose entrypoints):

    ```bash
    m2m-mindmap --input notes.md
    ```
  * Or generic runner:

    ```bash
    m2m --recipe mindmap_from_markdown --input notes.md
    ```

---

## 📂 Where Recipes Live

* **Inside the repo** (`mark2mind/recipes/*.toml`) → installed automatically with the package.
* You can also allow **external recipe dirs** (e.g. `--recipe-dir ./my_recipes`) so users can create custom flows.

---

## ✅ Beginner-Friendly Workflow With Recipes

Instead of learning all `[pipeline]` steps, a user can just run:

```bash
m2m-mindmap --input intro.md
```

and behind the scenes it loads `recipes/mindmap_from_markdown.toml`:

```toml
[pipeline]
preset = "mindmap"

[io]
input = "CHANGE_ME_TO_FILE.md"
output_dir = "output"
debug_dir  = "debug"

[llm]
provider = "deepseek"
model = "deepseek-chat"
api_key_env = "DEEPSEEK_API_KEY"
```

The same pattern works for:

* `m2m-qa` → `qa_from_markdown.toml`
* `m2m-list-subs` → `list_subtitles_in_dir.toml`
* `m2m-merge-subs` → `merge_subtitles_from_manifest.toml`
* `m2m-reformat` → `reformat_markdown.toml`
* `m2m-clarify` → `clarify_markdown.toml`
* `m2m-mindmap-detailed` → `detailed_mindmap_from_markdown.toml`

---

## 🔧 In the README (suggested section)

Add a **Recipes** section:

````markdown
### 🍳 Recipes (Predefined Workflows)

mark2mind ships with ready-to-use recipes so you don’t have to write configs by hand.

| Command            | Recipe file                       | Purpose |
|--------------------|-----------------------------------|---------|
| `m2m-list-subs`    | `list_subtitles_in_dir.toml`      | List subtitle files and generate manifest |
| `m2m-merge-subs`   | `merge_subtitles_from_manifest.toml` | Merge subtitles from manifest into one transcript |
| `m2m-reformat`     | `reformat_markdown.toml`          | Clean & reformat Markdown file |
| `m2m-clarify`      | `clarify_markdown.toml`           | Simplify/clarify Markdown text |
| `m2m-mindmap`      | `mindmap_from_markdown.toml`      | Generate a mindmap |
| `m2m-mindmap-detailed` | `detailed_mindmap_from_markdown.toml` | Mindmap + mapped content |
| `m2m-qa`           | `qa_from_markdown.toml`           | Q&A summary from Markdown |

#### Example

```bash
## Generate a mindmap
m2m-mindmap --input notes/intro.md

## Create Q&A notes
m2m-qa --input notes/chapter1.md

## List subtitles
m2m-list-subs --input data/subtitles/

## Merge subtitles (after list)
m2m-merge-subs --input data/subtitles/
````

Each recipe is just a TOML config. You can copy them and customize your own.

## 🔧 Advanced Usage

### How Pipelines Work

A pipeline is a sequence of **stages**. Presets are shortcuts for common flows.

You can override steps manually:

```bash
python -m mark2mind --config config.toml --steps chunk,tree,cluster,merge,refine,map
```

---

## 🔍 Stages Explained

| Stage               | Purpose                                          |
| ------------------- | ------------------------------------------------ |
| **chunk**           | Splits input into manageable pieces (by tokens). |
| **tree**            | Builds initial hierarchical tree of ideas.       |
| **cluster**         | Groups related nodes together.                   |
| **merge**           | Merges clusters into a unified structure.        |
| **refine**          | Refines tree with improved coherence.            |
| **map**             | Maps final tree into a detailed content mindmap. |
| **bullets**         | Converts chunks into bulleted text.              |
| **reformat**        | Rewrites chunks for readability.                 |
| **clean\_for\_map** | Cleans text specifically for mapping.            |
| **subs\_list**      | Lists subtitles and creates manifest.            |
| **subs\_merge**     | Merges subtitles into a Markdown transcript.     |

---

## ⚙️ Configuration

### Chunking

```toml
[chunk]
tokenizer_name = "gpt2"
max_tokens = 2000
overlap_tokens = 200
```

* **max\_tokens**: size of each chunk.
* **overlap\_tokens**: overlap for context preservation.

### Prompt Overrides

Use `[prompts.files]` to point to your own prompt text files:

```toml
[prompts.files]
chunk_tree = "custom_prompts/my_tree.txt"
qa_generate = "custom_prompts/my_questions.txt"
```

If a file is missing → falls back to built-in defaults.

### Tracing & Debugging

Enable tracing:

```bash
python -m mark2mind --config config.toml --enable-tracing
```

Outputs traces under:

```
debug/<run_name>/traces/
```

Useful for inspecting step-by-step interactions with the LLM.

### Runtime Tuning

```toml
[runtime]
force = true                 # re-run, ignore cache
executor_max_workers = 8     # control parallelism
min_delay_sec = 0.2          # delay between API calls
max_retries = 5
map_batch_override = 5       # override batch size for map stage
```

### Subtitles Flow

```toml
[io]
input = "data/subtitles"   # directory of .srt/.vtt files
manifest = "file_list.txt" # written by subs_list, read by subs_merge
include_html = true        # include .html transcripts
```

Pipeline:

1. `subs_list` → creates manifest of all subtitle files.
2. `subs_merge` → consumes manifest, outputs merged transcript.

---

## 🛠️ Debugging

* **Outputs** → always in `output/<run_name>/...`
* **Debug files** → in `debug/<run_name>/...`
* **Tracing** → enable with `--enable-tracing`.

Artifacts include intermediate chunks, QA pairs, and tree structures.

---

## ❓ FAQ / Troubleshooting

**Q: I get `Config error: [io].input is required`.**
A: Add `[io].input = "yourfile.md"` to `config.toml`.

---

**Q: Wrong mode: tried `subs_list` with a file input.**
A: Subtitles pipelines require `[io].input` to be a **directory**.

---

**Q: `subs_merge` fails: manifest not found.**
A: Run `subs_list` first, or set `[io].manifest` to point to an existing file.

---

**Q: API key error.**
A: Ensure you’ve set `DEEPSEEK_API_KEY` in your environment or in `[llm].api_key`.

---

**Q: My outputs are empty.**
A: Check `debug/<run_name>/...` for intermediate artifacts; re-run with `--force`.

---

## ✅ Summary

* Use **presets** for quick runs.
* Use **steps** for custom pipelines.
* All outputs live in `output/<run_name>/`.
* Debug/traces in `debug/<run_name>/`.
* Override prompts if you need custom behavior.

mark2mind makes it easy to go from **raw text** → **structured knowledge**.
