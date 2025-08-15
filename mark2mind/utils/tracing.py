import json
import uuid
import time
import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional, List

from langchain_core.callbacks.base import BaseCallbackHandler
from pydantic import BaseModel

def _json_safe(obj: Any) -> Any:
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        pass
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(v) for v in obj]
    return str(obj)

class LocalTracingHandler(BaseCallbackHandler):
    """
    Thread-safe local tracer.
    - Keeps a per-run event map so concurrent chains don't clobber each other.
    - Extracts a friendly name from kwargs (run_name/name), then tags/serialized/metadata.
    - Writes one JSON file per completed run and maintains an index.
    """

    def __init__(self, base_dir: str = "debug", file_id: Optional[str] = None, run_id: Optional[str] = None):
        self.file_id = file_id or "unknown"
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_id = run_id or f"{ts}-{uuid.uuid4().hex[:6]}"

        self.root = Path(base_dir) / self.file_id / "traces" / self.run_id
        self.root.mkdir(parents=True, exist_ok=True)

        self._index_path = self.root / "index.json"
        self._index: Dict[str, Any] = {
            "file_id": self.file_id,
            "run_id": self.run_id,
            "started_at": ts,
            "events": [],
        }

        # Concurrency primitives / state
        self._lock = Lock()
        self._seq = 0
        # Active events keyed by langchain run_id string
        self._active: Dict[str, Dict[str, Any]] = {}

    # ---------- internals ----------

    def _write_index(self) -> None:
        with self._index_path.open("w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2, ensure_ascii=False)

    def _next_seq(self) -> int:
        with self._lock:
            self._seq += 1
            return self._seq

    def _extract_name(
        self,
        serialized: Any,
        tags: Optional[List[str]],
        metadata: Optional[Dict[str, Any]],
        kwargs: Dict[str, Any],
    ) -> str:
        # Highest priority: explicit run name passed by LangChain
        for key in ("name", "run_name"):
            if key in kwargs and kwargs[key]:
                return str(kwargs[key])

        # Sometimes authors put name in metadata
        if metadata and isinstance(metadata, dict):
            for key in ("run_name", "name"):
                if metadata.get(key):
                    return str(metadata[key])

        # Pull class from tags (e.g., "class:AnswerQuestionsChain")
        if tags:
            for t in tags:
                if t.startswith("class:"):
                    return t.split(":", 1)[1]

        # Fall back to serialized structure
        if isinstance(serialized, dict):
            name = serialized.get("name")
            sid = serialized.get("id")
            if name:
                return str(name)
            if isinstance(sid, list) and sid:
                return str(sid[-1])
            if isinstance(sid, str):
                return sid

        return "unknown"

    def _event_filename(self, ev: Dict[str, Any]) -> str:
        # Build a compact, informative filename
        tag_bits = [
            t.replace(":", "-")
            for t in (ev.get("tags") or [])
            if any(t.startswith(p) for p in ("step:", "chunk:", "class:"))
        ]
        stem = "_".join(tag_bits)[:80] if tag_bits else ev.get("chain_name", "event")
        return f"{ev['seq']:03d}_{stem or 'event'}.json"

    # ---------- LangChain hooks ----------

    def on_chain_start(self, serialized, inputs, run_id=None, parent_run_id=None, tags=None, metadata=None, **kwargs):
        rid = str(run_id or uuid.uuid4())
        seq = self._next_seq()
        t0 = time.time()
        name = self._extract_name(serialized, tags, metadata, kwargs)

        ev = {
            "seq": seq,
            "chain_name": name,
            "inputs": _json_safe(inputs or {}),
            "tags": _json_safe(tags or []),
            "metadata": _json_safe(metadata or {}),
            "started_at": t0,
            "run_id": rid,
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
        }

        with self._lock:
            self._active[rid] = ev

    def on_chain_end(self, outputs, run_id=None, **kwargs):
        rid = str(run_id) if run_id else None
        if rid is None:
            return
        with self._lock:
            ev = self._active.pop(rid, None)
        if ev is None:
            return  # We missed the start; avoid crashing.

        ev["duration_sec"] = round(time.time() - float(ev["started_at"]), 3)
        ev["outputs"] = _json_safe(outputs)

        fname = self._event_filename(ev)
        path = self.root / fname
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(ev, f, indent=2, ensure_ascii=False)
        except TypeError as e:
            ev["outputs"] = f"<unserializable outputs: {e}>"
            with path.open("w", encoding="utf-8") as f:
                json.dump(ev, f, indent=2, ensure_ascii=False)

        with self._lock:
            self._index["events"].append(
                {
                    "seq": ev["seq"],
                    "file": fname,
                    "tags": ev.get("tags", []),
                    "metadata": ev.get("metadata", {}),
                    "chain_name": ev.get("chain_name", "unknown"),
                }
            )
            self._write_index()

    def on_chain_error(self, error, run_id=None, **kwargs):
        rid = str(run_id) if run_id else None
        if rid is None:
            return
        with self._lock:
            ev = self._active.get(rid)
        if ev is None:
            return
        ev["error"] = str(error)
        # Reuse end handler to flush
        self.on_chain_end(outputs={"error": str(error)}, run_id=run_id, **kwargs)

    # Capture token usage reliably per run
    def on_llm_end(self, response, run_id=None, **kwargs):
        rid = str(run_id) if run_id else None
        if rid is None:
            return
        usage = None
        if hasattr(response, "llm_output"):
            usage = getattr(response, "llm_output", {}).get("token_usage")
        if usage is None:
            return
        with self._lock:
            ev = self._active.get(rid)
            if ev is not None:
                ev["token_usage"] = _json_safe(usage)
