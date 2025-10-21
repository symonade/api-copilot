import os
import time
from typing import Dict, List, Optional

ChatTurn = Dict[str, object]  # role: str, text: str, meta: dict


class SessionStore:
    def __init__(self, max_turns: int = 30, max_sessions: int = 500, ttl_seconds: int = 86400):
        self.max_turns = max_turns
        self.max_sessions = max_sessions
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, Dict[str, object]] = {}  # sid -> {turns: List[ChatTurn], at: float}

    def _prune(self) -> None:
        now = time.time()
        # TTL prune
        for sid in list(self._store.keys()):
            at = self._store[sid].get("at", 0)  # type: ignore
            if now - float(at) > self.ttl_seconds:
                self._store.pop(sid, None)
        # Size prune (LRU)
        if len(self._store) > self.max_sessions:
            items = sorted(self._store.items(), key=lambda kv: kv[1].get("at", 0))
            for sid, _ in items[: max(0, len(self._store) - self.max_sessions)]:
                self._store.pop(sid, None)

    def append(self, session_id: str, role: str, text: str, meta: Optional[Dict] = None) -> List[ChatTurn]:
        rec = self._store.setdefault(session_id, {"turns": [], "at": time.time()})
        turns: List[ChatTurn] = rec["turns"]  # type: ignore
        turns.append({"role": role, "text": text, "meta": meta or {}})
        if len(turns) > self.max_turns:
            del turns[0 : len(turns) - self.max_turns]
        rec["at"] = time.time()
        self._prune()
        return list(turns)

    def get(self, session_id: str) -> List[ChatTurn]:
        rec = self._store.get(session_id)
        if not rec:
            return []
        rec["at"] = time.time()
        return list(rec.get("turns", []))  # type: ignore

    def reset(self, session_id: str) -> None:
        self._store.pop(session_id, None)
        self._prune()


SESSION_STORE = SessionStore(max_turns=int(os.getenv("MAX_TURNS", "20")))

