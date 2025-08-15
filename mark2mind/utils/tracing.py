# mark2mind/utils/tracing.py
import time, json, uuid, datetime
from pathlib import Path
from langchain_core.callbacks.base import BaseCallbackHandler
from pydantic import BaseModel

def _json_safe(obj):
    # already serializable?
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        pass
    # pydantic v2 model
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    # common containers
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(v) for v in obj]
    # fallback
    return str(obj)

class LocalTracingHandler(BaseCallbackHandler):
    def __init__(self, base_dir="debug", file_id: str | None = None, run_id: str | None = None):
        self.file_id = file_id or "unknown"
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_id = run_id or f"{ts}-{uuid.uuid4().hex[:6]}"
        self.root = Path(base_dir) / self.file_id / "traces" / self.run_id
        self.root.mkdir(parents=True, exist_ok=True)
        self._seq = 0
        self._cur = {}
        self._index_path = self.root / "index.json"
        self._index = {
            "file_id": self.file_id,
            "run_id": self.run_id,
            "started_at": ts,
            "events": []
        }

    def _write_index(self):
        with self._index_path.open("w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2, ensure_ascii=False)

    def _extract_name(self, serialized, tags, metadata) -> str:
        # Prefer explicit run_name you set via with_config(...)
        if metadata and isinstance(metadata, dict):
            rn = metadata.get("run_name") or metadata.get("name")
            if rn:
                return str(rn)
        # Fallbacks: tags like "class:TreeMergeChain"
        if tags:
            for t in tags:
                if t.startswith("class:"):
                    return t.split(":",1)[1]
        # Last resort: serialized (may be None or non-dict)
        if isinstance(serialized, dict):
            name = serialized.get("name")
            sid  = serialized.get("id")
            if name: return str(name)
            if isinstance(sid, list) and sid: return str(sid[-1])
            if isinstance(sid, str): return sid
        return "unknown"

    def on_chain_start(self, serialized, inputs, run_id=None, tags=None, metadata=None, **kwargs):
        self._seq += 1
        self._t0 = time.time()
        name = self._extract_name(serialized, tags, metadata)

        self._cur = {
            "seq": self._seq,
            "chain_name": name,
            "inputs": _json_safe(inputs or {}),
            "tags": _json_safe(tags or []),
            "metadata": _json_safe(metadata or {}),
            "started_at": self._t0,
            "run_id": str(run_id) if run_id else None,
        }

    def on_chain_end(self, outputs, run_id=None, **kwargs):
        self._cur["duration_sec"] = round(time.time() - self._t0, 3)
        self._cur["outputs"] = _json_safe(outputs)   # <— sanitize

        # friendly filename: 003_step:qa_chunk:7_Class.json
        tag_bits = [t.replace(":", "-") for t in self._cur.get("tags", []) if any(t.startswith(p) for p in ["step:", "chunk:", "class:"])]
        bits = "_".join(tag_bits)[:80] if tag_bits else self._cur.get("chain_name", "chain")
        fname = f"{self._cur['seq']:03d}_{bits or 'event'}.json"
        path = self.root / fname

        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(self._cur, f, indent=2, ensure_ascii=False)
        except TypeError as e:
            # last-ditch: stringify only the offending part and retry
            self._cur["outputs"] = f"<unserializable outputs: {e}>"
            with path.open("w", encoding="utf-8") as f:
                json.dump(self._cur, f, indent=2, ensure_ascii=False)

        # add to index
        self._index["events"].append({
            "seq": self._cur["seq"],
            "file": fname,
            "tags": self._cur.get("tags", []),
            "metadata": self._cur.get("metadata", {})
        })
        self._write_index()

    def on_chain_error(self, error, **kwargs):
        self._cur["error"] = str(error)
        self.on_chain_end(outputs={"error": str(error)})

    def on_llm_end(self, response, **kwargs):
        usage = getattr(response, "llm_output", {}).get("token_usage") if hasattr(response, "llm_output") else None
        if usage is not None:
            self._cur["token_usage"] = _json_safe(usage)  # <— sanitize

