from collections.abc import Iterator

import pytest

from yino_voice_agent.ops import WorkerRuntime, set_worker


@pytest.fixture(autouse=True)
def isolate_worker_runtime() -> Iterator[None]:
    set_worker(WorkerRuntime())
    yield
    set_worker(None)
