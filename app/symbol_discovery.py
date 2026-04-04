from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import duckdb

from app.config import settings

logger = logging.getLogger(__name__)

_INDEX_TTL = 600
_index_cache: tuple[float, list[SymbolMeta]] | None = None


@dataclass(frozen=True, slots=True)
class SymbolMeta:
    symbol: str
    rows: int
    first_date: str
    last_date: str
    avg_volume: float
    last_close: float
    return_1y: float


def _glob_pattern() -> str:
    return str(settings.parquet_dir / "*.parquet")


def build_metadata_index(force: bool = False) -> list[SymbolMeta]:
    global _index_cache

    if not force and _index_cache is not None:
        ts, cached = _index_cache
        if time.monotonic() - ts < _INDEX_TTL:
            return cached

    parquet_dir = settings.parquet_dir
    if not parquet_dir.exists():
        return []

    pattern = _glob_pattern()
    con = duckdb.connect()
    try:
        rows = con.execute(
            """
            SELECT
                replace(replace(regexp_extract(filename, '[^/\\\\]+$', 0), '_1d.parquet', ''), '.parquet', '') AS symbol,
                count(*)                       AS rows,
                min("Date")::VARCHAR           AS first_date,
                max("Date")::VARCHAR           AS last_date,
                avg("Volume")                  AS avg_volume,
                last("Close" ORDER BY "Date")  AS last_close,
                (last("Close" ORDER BY "Date") / first("Close" ORDER BY "Date") - 1) AS return_1y
            FROM read_parquet(?, filename=true)
            GROUP BY filename
            ORDER BY symbol
            """,
            [pattern],
        ).fetchall()
    except Exception:
        logger.exception("DuckDB metadata scan failed")
        return []
    finally:
        con.close()

    result = [
        SymbolMeta(
            symbol=str(r[0]).upper(),
            rows=int(r[1]),
            first_date=str(r[2]),
            last_date=str(r[3]),
            avg_volume=float(r[4]) if r[4] is not None else 0.0,
            last_close=float(r[5]) if r[5] is not None else 0.0,
            return_1y=float(r[6]) if r[6] is not None else 0.0,
        )
        for r in rows
    ]

    _index_cache = (time.monotonic(), result)
    logger.info("Symbol metadata index built: %d symbols", len(result))
    return result


def get_available_symbols_duckdb() -> set[str]:
    pattern = _glob_pattern()
    parquet_dir = settings.parquet_dir
    if not parquet_dir.exists():
        return set()

    con = duckdb.connect()
    try:
        rows = con.execute(
            """
            SELECT DISTINCT
                upper(replace(replace(regexp_extract(filename, '[^/\\\\]+$', 0), '_1d.parquet', ''), '.parquet', ''))
            FROM read_parquet(?, filename=true)
            """,
            [pattern],
        ).fetchall()
    except Exception:
        logger.exception("DuckDB available symbols scan failed")
        return set()
    finally:
        con.close()

    return {str(r[0]) for r in rows}


def search_symbols(
    query: str | None = None,
    min_volume: float | None = None,
    min_rows: int | None = None,
    sort_by: str = "symbol",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[SymbolMeta], int]:
    index = build_metadata_index()

    filtered = index
    if query:
        q = query.upper()
        filtered = [m for m in filtered if q in m.symbol]
    if min_volume is not None:
        filtered = [m for m in filtered if m.avg_volume >= min_volume]
    if min_rows is not None:
        filtered = [m for m in filtered if m.rows >= min_rows]

    sort_keys = {
        "symbol": lambda m: m.symbol,
        "volume": lambda m: -m.avg_volume,
        "rows": lambda m: -m.rows,
        "return": lambda m: -m.return_1y,
        "last_close": lambda m: -m.last_close,
    }
    key_fn = sort_keys.get(sort_by, sort_keys["symbol"])
    filtered.sort(key=key_fn)

    total = len(filtered)
    page = filtered[offset : offset + limit]
    return page, total


def clear_discovery_cache() -> None:
    global _index_cache
    _index_cache = None
