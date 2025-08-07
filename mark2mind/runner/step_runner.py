import json
import time
from pathlib import Path
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor

from mindmap_langchain.chains.generate_chunk_chain import ChunkTreeChain
from mindmap_langchain.chains.merge_tree_chain import TreeMergeChain
from mindmap_langchain.chains.refine_tree_chain import TreeRefineChain
from mindmap_langchain.chains.attach_content_chain import ContentMappingChain
from mindmap_langchain.chains.generate_questions_chain import GenerateQuestionsChain
from mindmap_langchain.chains.answer_questions_chain import AnswerQuestionsChain

from mindmap_langchain.utils.clustering import cluster_chunk_trees
from mindmap_langchain.utils.tree_helpers import assign_node_ids, insert_content_refs_into_tree
from mindmap_langchain.utils.debug import write_debug_file
from booqmark.chunker.markdown_chunker import chunk_markdown


class StepRunner:
    def __init__(
        self,
        input_file: str,
        file_id: str,
        steps: List[str],
        debug: bool,
        chunk_chain: ChunkTreeChain,
        merge_chain: TreeMergeChain,
        refine_chain: TreeRefineChain,
        content_chain: ContentMappingChain,
        qa_question_chain: GenerateQuestionsChain,
        qa_answer_chain: AnswerQuestionsChain,
        debug_dir: str = "debug",
        output_dir: str = "output",
        force: bool = False
    ):
        self.file_id = file_id
        self.steps = steps
        self.debug = debug
        self.chunk_chain = chunk_chain
        self.merge_chain = merge_chain
        self.refine_chain = refine_chain
        self.content_chain = content_chain
        self.qa_question_chain = qa_question_chain
        self.qa_answer_chain = qa_answer_chain
        self.force = force

        self.input_file = Path(input_file)
        self.debug_dir = Path(debug_dir) / file_id
        self.output_dir = Path(output_dir)
        self.debug_dir.mkdir(parents=True, exist_ok=True)

        self.text = self.input_file.read_text(encoding="utf-8")
        self.chunks: List[Dict] = []
        self.chunk_results: List[Dict] = []
        self.final_tree: Dict = {}

    def run(self):
        if "chunk" in self.steps:
            self.chunk()
        else:
            self._load_if_exists("chunks.json", attr="chunks")

        if "qa" in self.steps:
            self.generate_qa()
        else:
            self._load_if_exists("chunks_with_qa.json", attr="chunks")

        if "tree" in self.steps:
            self.generate_trees()

        if "cluster" in self.steps:
            self.cluster_chunks()

        if "merge" in self.steps:
            self.merge_clusters()

        if "refine" in self.steps:
            self.refine_tree()

        if "map" in self.steps:
            self.map_content()

        if self.final_tree:
            out_path = self.output_dir / f"{self.file_id}_mindmap.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(self.final_tree, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"✅ Mindmap saved to: {out_path}")

    def chunk(self):
        print("🔍 Chunking markdown...")
        self.chunks = chunk_markdown(self.text, max_tokens=1024, debug=self.debug, debug_dir=self.debug_dir)
        write_debug_file(self.debug_dir / "chunks.json", self.chunks)

    def generate_qa(self):
        print("🧠 Generating Q&A...")

        def add_qa(idx_chunk):
            idx, chunk = idx_chunk
            questions = self.qa_question_chain.invoke(chunk)
            answers = self.qa_answer_chain.invoke(chunk, questions)
            id_map = {b["element_id"]: b for b in chunk["blocks"]}
            for b in chunk["blocks"]:
                b["qa_pairs"] = []
            for qa in answers:
                if (eid := qa.get("element_id")) in id_map:
                    id_map[eid]["qa_pairs"].append(qa)
            return idx, chunk

        with ThreadPoolExecutor() as executor:
            updated = list(executor.map(add_qa, enumerate(self.chunks)))
        self.chunks = [chunk for _, chunk in sorted(updated)]
        write_debug_file(self.debug_dir / "chunks_with_qa.json", self.chunks)

    def generate_trees(self):
        print("🌲 Generating semantic trees...")

        def process(idx_chunk):
            idx, chunk = idx_chunk
            try:
                return self.chunk_chain.invoke(chunk)
            except Exception as e:
                print(f"❌ Error on chunk {idx}: {e}")
                return {"tree": {}, "tags": []}

        with ThreadPoolExecutor() as executor:
            self.chunk_results = list(executor.map(process, enumerate(self.chunks)))
        write_debug_file(self.debug_dir / "chunk_trees.json", self.chunk_results)

    def cluster_chunks(self):
        print("🧠 Clustering chunks...")
        cluster_count = max(2, len(self.chunk_results) // 4)
        self.clustered = cluster_chunk_trees(self.chunk_results, cluster_count)
        write_debug_file(self.debug_dir / "clusters.json", self.clustered)

    def merge_clusters(self):
        print("🔗 Merging trees within clusters...")

        def merge_group(group):
            trees = [i["tree"] for i in group if i["tree"]]
            while len(trees) > 1:
                merged = []
                for i in range(0, len(trees), 2):
                    if i+1 < len(trees):
                        merged_tree = self.merge_chain.invoke(trees[i], trees[i+1])
                        merged.append(merged_tree)
                    else:
                        merged.append(trees[i])
                trees = merged
            return trees[0] if trees else None

        with ThreadPoolExecutor() as executor:
            trees = list(executor.map(merge_group, self.clustered))
        self.cluster_trees = [t for t in trees if t]
        write_debug_file(self.debug_dir / "merged_clusters.json", self.cluster_trees)

    def refine_tree(self):
        print("🧹 Refining final tree...")

        def merge_all(trees: List[Dict]) -> Dict:
            while len(trees) > 1:
                merged = []
                for i in range(0, len(trees), 2):
                    if i+1 < len(trees):
                        merged.append(self.merge_chain.invoke(trees[i], trees[i+1]))
                    else:
                        merged.append(trees[i])
                trees = merged
            return trees[0]

        merged = merge_all(self.cluster_trees)
        refined = self.refine_chain.invoke(merged)
        assign_node_ids(refined)
        self.final_tree = refined
        write_debug_file(self.debug_dir / "refined_tree.json", refined)

    def map_content(self):
        print("📎 Mapping content to final tree...")

        def attach(idx_chunk):
            idx, chunk = idx_chunk
            if not chunk["blocks"]:
                return
            mapped = self.content_chain.invoke(self.final_tree, chunk["blocks"])
            insert_content_refs_into_tree(self.final_tree, mapped)

        with ThreadPoolExecutor() as executor:
            list(executor.map(attach, enumerate(self.chunks)))
        write_debug_file(self.debug_dir / "final_tree.json", self.final_tree)

    def _load_if_exists(self, filename: str, attr: str):
        path = self.debug_dir / filename
        if not self.force and path.exists():
            with open(path, "r", encoding="utf-8") as f:
                setattr(self, attr, json.load(f))