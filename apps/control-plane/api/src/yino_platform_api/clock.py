from collections.abc import Callable
from datetime import UTC, datetime

NowProvider = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)
