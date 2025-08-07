import time
import json
from pathlib import Path
from langchain_core.callbacks.base import BaseCallbackHandler
from typing import Dict, List, Any, Optional

class LocalTracingHandler(BaseCallbackHandler):
    def __init__(self, trace_dir: Optional[str] = "debug/traces"):
        self.logs: List[Dict[str, Any]] = []
        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)

    def on_chain_start(self, serialized, inputs, **kwargs):
        self._start_time = time.time()
        self._inputs = inputs
        self._chain_name = serialized.get("name", "unknown_chain")

    def on_chain_end(self, outputs, **kwargs):
        elapsed = time.time() - self._start_time
        log_entry = {
            "chain_name": self._chain_name,
            "inputs": self._inputs,
            "outputs": outputs,
            "duration_sec": round(elapsed, 3),
        }
        self.logs.append(log_entry)

        ts = int(time.time() * 1000)
        out_path = self.trace_dir / f"{self._chain_name}_{ts}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(log_entry, f, indent=2, ensure_ascii=False)

    def on_llm_end(self, response, **kwargs):
        usage = response.llm_output.get("token_usage") if hasattr(response, "llm_output") else None
        if usage and self.logs:
            self.logs[-1]["token_usage"] = usage
