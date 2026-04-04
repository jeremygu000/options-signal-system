"""In-process request metrics for observability.

Tracks request counts, latency percentiles, error rates, and status-code breakdown
without requiring an external metrics backend (Prometheus, Datadog, etc.).
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class _LatencyBucket:
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0
    samples: list[float] = field(default_factory=list)

    _MAX_SAMPLES: int = 1000

    def record(self, ms: float) -> None:
        self.count += 1
        self.total_ms += ms
        if ms < self.min_ms:
            self.min_ms = ms
        if ms > self.max_ms:
            self.max_ms = ms
        if len(self.samples) < self._MAX_SAMPLES:
            self.samples.append(ms)

    def percentile(self, p: float) -> float:
        if not self.samples:
            return 0.0
        sorted_s = sorted(self.samples)
        idx = int(len(sorted_s) * p / 100)
        return sorted_s[min(idx, len(sorted_s) - 1)]

    def avg_ms(self) -> float:
        return self.total_ms / self.count if self.count else 0.0


class RequestMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._total_requests: int = 0
        self._status_codes: dict[int, int] = defaultdict(int)
        self._latency = _LatencyBucket()
        self._per_path: dict[str, _LatencyBucket] = defaultdict(_LatencyBucket)
        self._errors: int = 0
        self._start_time: float = time.monotonic()

    def record(self, path: str, status_code: int, latency_ms: float) -> None:
        with self._lock:
            self._total_requests += 1
            self._status_codes[status_code] += 1
            self._latency.record(latency_ms)
            self._per_path[path].record(latency_ms)
            if status_code >= 500:
                self._errors += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            uptime_s = time.monotonic() - self._start_time
            top_paths = sorted(self._per_path.items(), key=lambda kv: kv[1].count, reverse=True)[:10]
            return {
                "total_requests": self._total_requests,
                "error_count": self._errors,
                "error_rate": round(self._errors / self._total_requests, 4) if self._total_requests else 0.0,
                "uptime_seconds": round(uptime_s, 1),
                "status_codes": dict(self._status_codes),
                "latency": {
                    "avg_ms": round(self._latency.avg_ms(), 2),
                    "min_ms": round(self._latency.min_ms, 2) if self._latency.count else 0.0,
                    "max_ms": round(self._latency.max_ms, 2),
                    "p50_ms": round(self._latency.percentile(50), 2),
                    "p95_ms": round(self._latency.percentile(95), 2),
                    "p99_ms": round(self._latency.percentile(99), 2),
                },
                "top_paths": [
                    {
                        "path": path,
                        "count": bucket.count,
                        "avg_ms": round(bucket.avg_ms(), 2),
                        "p95_ms": round(bucket.percentile(95), 2),
                    }
                    for path, bucket in top_paths
                ],
            }

    def reset(self) -> None:
        with self._lock:
            self._total_requests = 0
            self._status_codes.clear()
            self._latency = _LatencyBucket()
            self._per_path.clear()
            self._errors = 0
            self._start_time = time.monotonic()


metrics = RequestMetrics()
