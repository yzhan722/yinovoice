"""Synthetic latency summaries. No metrics backend, no wall-clock sleeps."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LatencySummary:
    count: int
    min: float
    median: float
    p50: float
    p90: float
    p95: float
    p99: float
    max: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "count": self.count,
            "min": self.min,
            "median": self.median,
            "p50": self.p50,
            "p90": self.p90,
            "p95": self.p95,
            "p99": self.p99,
            "max": self.max,
        }

    def format_block(self, name: str) -> str:
        return (
            f"{name}\n"
            f"count: {self.count}\n"
            f"p50: {self.p50:.6f}\n"
            f"p95: {self.p95:.6f}\n"
            f"p99: {self.p99:.6f}"
        )


def percentile(values: Sequence[float], p: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one sample")
    if p < 0 or p > 100:
        raise ValueError("percentile must be in [0, 100]")
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (p / 100.0) * (len(ordered) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return float(ordered[low])
    weight = rank - low
    return float(ordered[low]) * (1.0 - weight) + float(ordered[high]) * weight


def summarize(values: Sequence[float]) -> LatencySummary:
    if not values:
        raise ValueError("summarize requires at least one sample")
    ordered = sorted(values)
    p50 = percentile(ordered, 50)
    return LatencySummary(
        count=len(ordered),
        min=float(ordered[0]),
        median=p50,
        p50=p50,
        p90=percentile(ordered, 90),
        p95=percentile(ordered, 95),
        p99=percentile(ordered, 99),
        max=float(ordered[-1]),
    )
