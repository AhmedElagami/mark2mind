# FILE: mark2mind/pipeline/stages/enrich_notes.py
from __future__ import annotations
from typing import Dict, List, Tuple
from concurrent.futures import as_completed
import json
from ..core.context import RunContext
from ..core.artifacts import ArtifactStore
from ..core.progress import ProgressReporter
from ..core.retry import Retryer
from ..core.llm_pool import LLMFactoryPool
from ..core.executor_provider import ExecutorProvider
from mark2mind.chains.note_generation_chains import NoteLeafChain, NoteBranchChain, PrereqPickChain
from mark2mind.utils.tree_helper import assign_node_ids
from datetime import datetime

LEAF_SECTIONS = ["## Summary","## Purpose","## Concept","## Pre-reqs","## How-to","## Reference","## Checks","## Failure modes","## Security/Quality","## See also"]
BRANCH_SECTIONS = ["## Scope","## Map","## Choice guide","## Workflows","## Cross-cutting pitfalls","## Children"]

class EnrichMarkmapNotesStage:
    ARTIFACT = "enriched_tree.json"

    def __init__(self, llm_pool: LLMFactoryPool, retryer: Retryer, callbacks=None):
        self.llm_pool = llm_pool
        self.retryer = retryer
        self.callbacks = callbacks

    def _walk(self, root: Dict) -> Tuple[List[Dict], Dict[str,str], Dict[str,List[str]], Dict[str,str], Dict[str,List[str]]]:
        # returns (nodes list), title path map, children graph, parent graph, depth lists
        order: List[Dict] = []
        title_path: Dict[str,str] = {}
        graph_children: Dict[str,List[str]] = {}
        graph_parent: Dict[str,str] = {}
        depth_map: Dict[str,int] = {}
        path_titles_map: Dict[str,List[str]] = {}

        def rec(n: Dict, path: List[str], depth: int, parent_id: str|None):
            nid = n["node_id"]
            depth_map[nid] = depth
            path_titles_map[nid] = path + [n.get("title") or ""]
            title_path[nid] = "/".join(path_titles_map[nid])
            graph_children[nid] = [c["node_id"] for c in n.get("children",[])]
            if parent_id:
                graph_parent[nid] = parent_id
            row = {"id": nid, "node": n}
            order.append(row)
            for c in n.get("children",[]):
                rec(c, path + [n.get("title") or ""], depth+1, nid)
        rec(root, [], 0, None)
        return order, title_path, graph_children, graph_parent, depth_map

    def _node_type(self, nid: str, depth_map: Dict[str,int], graph_children: Dict[str,List[str]]) -> str:
        if not graph_children.get(nid):
            return "leaf"
        if depth_map.get(nid,0) <= 1:
            return "hub"
        return "branch"

    def _levels(self, ids: List[str], depth_map: Dict[str,int]) -> Dict[int,List[str]]:
        lv: Dict[int,List[str]] = {}
        for nid in ids:
            d = depth_map[nid]
            lv.setdefault(d, []).append(nid)
        return lv

    def _mk_frontmatter(self, node_id: str, ntype: str, parent_link: str|None, child_links: List[str], prereq_links: List[str], summary: str, model_id: str, run_id: str) -> str:
        lines = ["---",
                 f"id: {node_id}",
                 f"type: {ntype}",
                 f"parent: {parent_link if parent_link else ''}".rstrip()]
        lines.append("children:")
        for c in child_links:
            lines.append(f"  - {c}")
        lines.append("prereqs:")
        for p in prereq_links:
            lines.append(f"  - {p}")
        lines.append(f"summary: {summary}")
        lines.append(f"model: {model_id}")
        lines.append(f"run_id: {run_id}")
        lines.append("---")
        return "\n".join(lines)

    def _wikilink(self, path_str: str) -> str:
        return f"[[{path_str}]]"

    def run(self, ctx: RunContext, store: ArtifactStore, progress: ProgressReporter, *, use_debug_io: bool, executor: ExecutorProvider) -> RunContext:
        if not ctx.final_tree:
            return ctx

        assign_node_ids(ctx.final_tree)
        nodes, title_path, graph_children, graph_parent, depth_map = self._walk(ctx.final_tree)
        ids = [n["id"] for n in nodes]
        levels = self._levels(ids, depth_map)
        llm = self.llm_pool.get()
        leaf_chain = NoteLeafChain(llm, callbacks=self.callbacks)
        branch_chain = NoteBranchChain(llm, callbacks=self.callbacks)
        prereq_chain = PrereqPickChain(llm, callbacks=self.callbacks)

        # compute path strings once
        path_str = {nid: title_path[nid].replace("/", "/") for nid in ids}

        # generate leaves deepest-first
        deepest = sorted(levels.keys(), reverse=True)
        summaries: Dict[str,str] = {}
        model_id = getattr(llm, "model", "provider/model")
        run_id = getattr(ctx, "run_id", "manual")

        def gen_leaf(nid: str) -> Tuple[str,str]:
            n = next(x["node"] for x in nodes if x["id"] == nid)
            required_sections = "\n".join(LEAF_SECTIONS)
            parent_id = graph_parent.get(nid)
            parent_path = path_str[parent_id] if parent_id else ""
            body = self.retryer.call(
                leaf_chain.invoke,
                node_title=n.get("title") or "Untitled",
                node_path=path_str[nid],
                parent_path=parent_path,
                required_sections=required_sections,
                style_rules="summary<=80; see_also<=5; no_frontmatter",
                known_facts=""
            )
            # extract summary line
            sum_line = ""
            for line in body.splitlines():
                if line.strip().lower().startswith("## summary"):
                    # next non-empty line(s) until next section
                    sum_line = ""
                elif sum_line is not None:
                    if line.startswith("## "):
                        break
                    if line.strip():
                        sum_line += ((" " if sum_line else "") + line.strip())
            return nid, (body, (sum_line or "")[:480])

        for depth in deepest:
            leaf_ids = [nid for nid in levels[depth] if self._node_type(nid, depth_map, graph_children) == "leaf"]
            if not leaf_ids: continue
            t = progress.start(f"Generating leaves at depth {depth}", total=len(leaf_ids))
            results = {}
            with executor.get() as pool:
                futs = [pool.submit(gen_leaf, nid) for nid in leaf_ids]
                for f in as_completed(futs):
                    nid, (body, summary) = f.result()
                    results[nid] = (body, summary)
                    progress.advance(t)
            progress.finish(t)
            for nid, (body, summary) in results.items():
                summaries[nid] = summary

        # generate branches/hubs upward
        for depth in sorted(levels.keys()):
            non_leaf = [nid for nid in levels[depth] if self._node_type(nid, depth_map, graph_children) != "leaf"]
            if not non_leaf: continue
            t = progress.start(f"Generating branches/hubs at depth {depth}", total=len(non_leaf))
            for nid in non_leaf:
                n = next(x["node"] for x in nodes if x["id"] == nid)
                kids = graph_children.get(nid, [])
                digest = []
                for cid in kids:
                    digest.append(f"- {next(x['node'] for x in nodes if x['id']==cid).get('title','Untitled')} :: [[{path_str[cid]}]] :: {summaries.get(cid,'')}")
                transclusion_hint = "- After the sections, include one transclusion line per child: ![[{}#Summary]]".format("]]\n![[ ".join(path_str[c] for c in kids)) if kids else ""
                body = self.retryer.call(
                    branch_chain.invoke,
                    node_title=n.get("title") or "Untitled",
                    node_path=path_str[nid],
                    children_digest="\n".join(digest),
                    required_sections="\n".join(BRANCH_SECTIONS),
                    transclusion_hint=transclusion_hint
                )
                # store in summaries optionally blank
                summaries[nid] = summaries.get(nid,"")
                n.setdefault("content_refs", []).append({
                    "element_id": f"note::{nid}",
                    "type": "paragraph",
                    "element_caption": "Teaching note",
                    "markdown": "",  # frontmatter+body injected later
                    "created_at": datetime.utcnow().isoformat(timespec="seconds")+"Z",
                })
                n["_generated_body"] = body  # stash temporarily
                progress.advance(t)
            progress.finish(t)

        # pick prereqs per leaf
        graph_children_json = json.dumps(graph_children)
        for nid in ids:
            if self._node_type(nid, depth_map, graph_children) != "leaf":
                continue
            target = {
                "id": nid,
                "title": next(x["node"] for x in nodes if x["id"]==nid).get("title","Untitled"),
                "path": path_str[nid],
                "summary": summaries.get(nid,"")[:480]
            }
            # build candidate pool
            parent = graph_parent.get(nid)
            siblings = [s for s in (graph_children.get(parent,[]) if parent else []) if s != nid]
            grandparent = graph_parent.get(parent) if parent else None
            cousins = []
            if grandparent:
                for sib_parent in graph_children.get(grandparent, []):
                    cousins.extend([c for c in graph_children.get(sib_parent, []) if c not in graph_children.get(nid,[])])
            candidates = list(dict.fromkeys([*siblings, *cousins]))[:30]
            cand_objs = [
                {"id": cid, "title": next(x["node"] for x in nodes if x["id"]==cid).get("title","Untitled"),
                 "path": path_str[cid], "summary": summaries.get(cid,"")[:480]}
                for cid in candidates if cid != nid
            ]
            chosen = self.retryer.call(
                prereq_chain.invoke,
                target=target,
                candidates_json=json.dumps(cand_objs, ensure_ascii=False),
                graph_children_json=graph_children_json
            )
            # validate
            chosen = [c for c in chosen if c in ids and c != nid and c not in set(graph_children.get(nid,[]))][:5]
            target_node = next(x["node"] for x in nodes if x["id"]==nid)
            target_node["_prereq_ids"] = chosen

        # embed frontmatter+body into a single synthetic content_ref per node
        for nid in ids:
            n = next(x["node"] for x in nodes if x["id"]==nid)
            ntype = self._node_type(nid, depth_map, graph_children)
            parent_id = graph_parent.get(nid)
            parent_link = self._wikilink(path_str[parent_id]) if parent_id else ""
            child_links = [self._wikilink(path_str[c]) for c in graph_children.get(nid,[])]
            prereq_links = [self._wikilink(path_str[p]) for p in (n.get("_prereq_ids") or [])]
            fm = self._mk_frontmatter(
                node_id=nid,
                ntype=ntype,
                parent_link=parent_link,
                child_links=child_links,
                prereq_links=prereq_links,
                summary=(summaries.get(nid,"") or "")[:480],
                model_id=str(model_id),
                run_id=str(run_id),
            )
            body = n.pop("_generated_body", f"# {n.get('title') or 'Untitled'}\n")
            if not body.lstrip().startswith("# "):
                body = f"# {n.get('title') or 'Untitled'}\n{body}"
            synthetic = f"{fm}\n{body}"
            # ensure only one synthetic note ref and keep existing refs
            refs = n.setdefault("content_refs", [])
            # put synthetic first
            refs.insert(0, {
                "element_id": f"note::{nid}",
                "type": "paragraph",
                "element_caption": "Teaching note",
                "markdown": synthetic,
                "created_at": datetime.utcnow().isoformat(timespec="seconds")+"Z",
            })

        store.save_debug(self.ARTIFACT, ctx.final_tree)
        return ctx
