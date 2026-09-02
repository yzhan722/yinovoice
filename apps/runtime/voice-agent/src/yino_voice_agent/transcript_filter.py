"""Drop empty, noise-only, and duplicate-final transcripts before the model."""

from __future__ import annotations

import re
from collections import OrderedDict

_SPOKEN = re.compile(r"[\w\u3400-\u9fff]", re.UNICODE)
_MAX_SEEN_IDS = 256


class FinalTranscriptGate:
    """Accept one final per stable item_id. Do not fuzzy-dedupe spoken repeats."""

    def __init__(self, *, max_ids: int = _MAX_SEEN_IDS) -> None:
        self._max_ids = max_ids
        self._seen: OrderedDict[str, None] = OrderedDict()

    def accept(self, text: str, item_id: str | None = None) -> bool:
        spoken = (text or "").strip()
        if not spoken or not _SPOKEN.search(spoken):
            return False
        if item_id:
            if item_id in self._seen:
                return False
            self._seen[item_id] = None
            overflow = len(self._seen) - self._max_ids
            if overflow > 0:
                for _ in range(overflow):
                    self._seen.popitem(last=False)
        return True

    @property
    def seen_count(self) -> int:
        return len(self._seen)
