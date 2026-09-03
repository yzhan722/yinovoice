from yino_voice_agent.bounded_ids import DEFAULT_ID_WINDOW, BoundedIdWindow


def test_duplicate_add_does_not_grow() -> None:
    window = BoundedIdWindow(capacity=8)
    assert window.add("resp-1") is True
    assert window.add("resp-1") is False
    assert len(window) == 1
    assert "resp-1" in window


def test_capacity_evicts_oldest_and_keeps_latest() -> None:
    window = BoundedIdWindow(capacity=4)
    for index in range(10):
        window.add(f"resp-{index}")
    assert len(window) == 4
    assert "resp-0" not in window
    assert "resp-5" not in window
    assert "resp-6" in window
    assert "resp-9" in window


def test_discard_removes_without_unbounding() -> None:
    window = BoundedIdWindow(capacity=4)
    window.add("resp-a")
    window.add("resp-b")
    window.discard("resp-a")
    assert "resp-a" not in window
    assert "resp-b" in window
    assert len(window) == 1
    window.add("resp-c")
    assert len(window) == 2


def test_default_capacity_matches_usage_window() -> None:
    window = BoundedIdWindow()
    assert window.capacity == DEFAULT_ID_WINDOW
    for index in range(DEFAULT_ID_WINDOW + 50):
        window.add(f"id-{index}")
    assert len(window) == DEFAULT_ID_WINDOW
    assert f"id-{DEFAULT_ID_WINDOW + 49}" in window
    assert "id-0" not in window


def test_clear_empties_window() -> None:
    window = BoundedIdWindow(capacity=4)
    window.add("resp-1")
    window.clear()
    assert len(window) == 0
    assert "resp-1" not in window
