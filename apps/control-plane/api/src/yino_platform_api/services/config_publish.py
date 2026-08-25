from __future__ import annotations

from typing import Any


def config_diff_changes(
    current_snapshot: dict[str, Any],
    published_snapshot: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    current_flat = _flatten(current_snapshot)
    published_flat = _flatten(published_snapshot or {})
    keys = sorted(set(current_flat) | set(published_flat))
    changes: list[dict[str, Any]] = []
    for key in keys:
        before = published_flat.get(key)
        after = current_flat.get(key)
        if before != after:
            changes.append({"field": key, "before": before, "after": after})
    return changes


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, nested in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            out.update(_flatten(nested, path))
        return out
    if prefix:
        return {prefix: value}
    return {}
