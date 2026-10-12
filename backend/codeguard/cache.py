"""
High-performance fix cache for CodeGuard AI.
Keyed by content hash, vulnerability fingerprint, and rule ID.
Ensures identical and recurring vulnerability patterns are remediated in 0 ms with 0 tokens.
"""

import hashlib
import json
import time
from typing import Optional, Dict, Any
from pathlib import Path


class FixCache:
    def __init__(self, cache_file: str = ".codeguard/fix_cache.json"):
        self.cache_file = Path(cache_file)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Dict[str, Any]] = self._load()

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save(self):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except Exception:
            pass

    def compute_key(self, rule_id: str, snippet: str, language: str) -> str:
        raw = f"{rule_id}:{language}:{snippet.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, rule_id: str, snippet: str, language: str) -> Optional[Dict[str, Any]]:
        key = self.compute_key(rule_id, snippet, language)
        hit = self._cache.get(key)
        if hit:
            hit["cache_hit"] = True
            return hit
        return None

    def put(self, rule_id: str, snippet: str, language: str, patch_data: Dict[str, Any]):
        key = self.compute_key(rule_id, snippet, language)
        patch_data["cached_at"] = time.time()
        self._cache[key] = patch_data
        self._save()

    def clear(self):
        self._cache.clear()
        self._save()
