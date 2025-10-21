from __future__ import annotations

import csv
from collections import deque, defaultdict
from datetime import datetime, UTC
from typing import Deque, Dict, List, Optional


class Analytics:
    def __init__(self, max_events: int = 1000, max_days: int = 30):
        self.max_events = max_events
        self.max_days = max_days
        self._events: Deque[Dict] = deque(maxlen=max_events)
        # daily aggregates keyed by UTC date string YYYY-MM-DD
        self._daily: Dict[str, Dict] = defaultdict(lambda: {
            "requests_total": 0,
            "unique_sessions": set(),
            "share_clicks": 0,
            "latency_sum_ms": 0,
            "latency_count": 0,
            "avg_latency_ms": 0,
            "tool_calls": 0,
            "errors_by_type": defaultdict(int),
        })

    @staticmethod
    def _utc_day_str(ts: Optional[datetime] = None) -> str:
        ts = ts or datetime.now(UTC)
        return ts.strftime("%Y-%m-%d")

    def _trim_days(self) -> None:
        # retain only last max_days
        keys = sorted(self._daily.keys())
        if len(keys) > self.max_days:
            for k in keys[: len(keys) - self.max_days]:
                self._daily.pop(k, None)

    def record_event(
        self,
        session_id: str,
        route: str,
        latency_ms: int,
        selected_api: Optional[str],
        ok: bool,
        err_type: Optional[str] = None,
        tool_calls: int = 0,
    ) -> None:
        ts = datetime.now(UTC)
        day = self._utc_day_str(ts)
        ev = {
            "ts": ts.isoformat(),
            "sid": session_id,
            "route": route,
            "latency_ms": latency_ms,
            "selected_api": selected_api,
            "result": "ok" if ok else "error",
            "err_type": err_type or "",
        }
        self._events.append(ev)

        d = self._daily[day]
        d["requests_total"] += 1
        d["unique_sessions"].add(session_id)
        d["latency_sum_ms"] += latency_ms
        d["latency_count"] += 1
        d["avg_latency_ms"] = int(d["latency_sum_ms"] / max(1, d["latency_count"]))
        d["tool_calls"] += int(tool_calls)
        if not ok and err_type:
            d["errors_by_type"][err_type] += 1
        self._trim_days()

    def record_share(self) -> None:
        day = self._utc_day_str()
        d = self._daily[day]
        d["share_clicks"] += 1
        self._trim_days()

    def snapshot_daily(self) -> List[Dict]:
        out: List[Dict] = []
        for day in sorted(self._daily.keys()):
            d = self._daily[day]
            out.append({
                "day": day,
                "requests_total": d["requests_total"],
                "unique_sessions": len(d["unique_sessions"]),
                "share_clicks": d["share_clicks"],
                "avg_latency_ms": d["avg_latency_ms"],
                "tool_calls": d["tool_calls"],
                "errors_by_type": dict(d["errors_by_type"]),
            })
        return out

    def recent_events(self, n: int = 200) -> List[Dict]:
        return list(self._events)[-n:]

    def to_csv(self) -> str:
        rows = self.snapshot_daily()
        if not rows:
            return "day,requests_total,unique_sessions,share_clicks,avg_latency_ms,tool_calls,errors_json\n"
        # flatten errors_by_type as JSON
        out_lines: List[str] = []
        out_lines.append("day,requests_total,unique_sessions,share_clicks,avg_latency_ms,tool_calls,errors_json")
        for r in rows:
            errors_json = json_dumps(r.get("errors_by_type", {}))
            line = f"{r['day']},{r['requests_total']},{r['unique_sessions']},{r['share_clicks']},{r['avg_latency_ms']},{r['tool_calls']},{errors_json}"
            out_lines.append(line)
        return "\n".join(out_lines) + "\n"


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, separators=(",", ":"))


ANALYTICS = Analytics()

