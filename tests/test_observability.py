from __future__ import annotations

import time

from app.metrics import RequestMetrics, _LatencyBucket


class TestLatencyBucket:
    def test_record_updates_stats(self) -> None:
        b = _LatencyBucket()
        b.record(10.0)
        b.record(20.0)
        b.record(30.0)
        assert b.count == 3
        assert b.min_ms == 10.0
        assert b.max_ms == 30.0
        assert b.avg_ms() == 20.0

    def test_percentile_empty(self) -> None:
        b = _LatencyBucket()
        assert b.percentile(50) == 0.0

    def test_percentile_values(self) -> None:
        b = _LatencyBucket()
        for i in range(1, 101):
            b.record(float(i))
        assert b.percentile(50) == 51.0
        assert b.percentile(95) == 96.0
        assert b.percentile(99) == 100.0

    def test_max_samples_cap(self) -> None:
        b = _LatencyBucket()
        for i in range(1200):
            b.record(float(i))
        assert b.count == 1200
        assert len(b.samples) == b._MAX_SAMPLES


class TestRequestMetrics:
    def test_record_and_snapshot(self) -> None:
        m = RequestMetrics()
        m.record("/api/v1/health", 200, 5.0)
        m.record("/api/v1/health", 200, 10.0)
        m.record("/api/v1/signals", 500, 100.0)

        snap = m.snapshot()
        assert snap["total_requests"] == 3
        assert snap["error_count"] == 1
        assert snap["error_rate"] == round(1 / 3, 4)
        assert snap["status_codes"] == {200: 2, 500: 1}

        latency = snap["latency"]
        assert isinstance(latency, dict)
        assert latency["min_ms"] == 5.0
        assert latency["max_ms"] == 100.0

    def test_top_paths_sorted_by_count(self) -> None:
        m = RequestMetrics()
        for _ in range(5):
            m.record("/a", 200, 1.0)
        for _ in range(10):
            m.record("/b", 200, 1.0)
        for _ in range(3):
            m.record("/c", 200, 1.0)

        snap = m.snapshot()
        top = snap["top_paths"]
        assert isinstance(top, list)
        assert top[0]["path"] == "/b"
        assert top[1]["path"] == "/a"
        assert top[2]["path"] == "/c"

    def test_reset(self) -> None:
        m = RequestMetrics()
        m.record("/x", 200, 5.0)
        m.reset()

        snap = m.snapshot()
        assert snap["total_requests"] == 0
        assert snap["error_count"] == 0

    def test_uptime_increases(self) -> None:
        m = RequestMetrics()
        time.sleep(0.05)
        snap = m.snapshot()
        assert snap["uptime_seconds"] >= 0.04  # type: ignore[operator]

    def test_empty_snapshot(self) -> None:
        m = RequestMetrics()
        snap = m.snapshot()
        assert snap["total_requests"] == 0
        assert snap["error_rate"] == 0.0
        latency = snap["latency"]
        assert isinstance(latency, dict)
        assert latency["avg_ms"] == 0.0
        assert latency["min_ms"] == 0.0


class TestLoggingConfig:
    def test_setup_logging_console(self) -> None:
        from app.logging_config import setup_logging

        setup_logging(json_format=False)
        import logging

        root = logging.getLogger()
        assert root.level == logging.INFO
        assert len(root.handlers) >= 1

    def test_setup_logging_json(self) -> None:
        from app.logging_config import setup_logging

        setup_logging(json_format=True)
        import logging

        root = logging.getLogger()
        assert root.level == logging.INFO
