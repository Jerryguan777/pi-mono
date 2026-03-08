"""Unit tests for KillRing."""

from pi_tui.kill_ring import KillRing


class TestKillRingInitialState:
    def test_empty_ring_has_length_zero(self) -> None:
        kr = KillRing()
        assert kr.length == 0

    def test_empty_ring_peek_returns_none(self) -> None:
        kr = KillRing()
        assert kr.peek() is None


class TestPushAndPeek:
    def test_push_single_entry(self) -> None:
        kr = KillRing()
        kr.push("hello", prepend=False)
        assert kr.peek() == "hello"
        assert kr.length == 1

    def test_push_multiple_entries_peek_returns_last(self) -> None:
        kr = KillRing()
        kr.push("first", prepend=False)
        kr.push("second", prepend=False)
        kr.push("third", prepend=False)
        assert kr.peek() == "third"
        assert kr.length == 3

    def test_push_empty_string_is_noop(self) -> None:
        kr = KillRing()
        kr.push("", prepend=False)
        assert kr.length == 0
        assert kr.peek() is None

    def test_push_empty_string_does_not_affect_existing(self) -> None:
        kr = KillRing()
        kr.push("existing", prepend=False)
        kr.push("", prepend=False, accumulate=True)
        assert kr.length == 1
        assert kr.peek() == "existing"


class TestAccumulate:
    def test_accumulate_prepend_true_prepends_text(self) -> None:
        """Backward deletion: new text goes before existing entry."""
        kr = KillRing()
        kr.push("world", prepend=True)
        kr.push("hello ", prepend=True, accumulate=True)
        assert kr.length == 1
        assert kr.peek() == "hello world"

    def test_accumulate_prepend_false_appends_text(self) -> None:
        """Forward deletion: new text goes after existing entry."""
        kr = KillRing()
        kr.push("hello", prepend=False)
        kr.push(" world", prepend=False, accumulate=True)
        assert kr.length == 1
        assert kr.peek() == "hello world"

    def test_accumulate_multiple_times_prepend(self) -> None:
        kr = KillRing()
        kr.push("c", prepend=True)
        kr.push("b", prepend=True, accumulate=True)
        kr.push("a", prepend=True, accumulate=True)
        assert kr.length == 1
        assert kr.peek() == "abc"

    def test_accumulate_multiple_times_append(self) -> None:
        kr = KillRing()
        kr.push("a", prepend=False)
        kr.push("b", prepend=False, accumulate=True)
        kr.push("c", prepend=False, accumulate=True)
        assert kr.length == 1
        assert kr.peek() == "abc"

    def test_accumulate_on_empty_ring_creates_new_entry(self) -> None:
        kr = KillRing()
        kr.push("text", prepend=False, accumulate=True)
        assert kr.length == 1
        assert kr.peek() == "text"

    def test_accumulate_false_always_adds_new_entry(self) -> None:
        kr = KillRing()
        kr.push("first", prepend=False)
        kr.push("second", prepend=False, accumulate=False)
        assert kr.length == 2
        assert kr.peek() == "second"


class TestRotate:
    def test_rotate_empty_ring_is_noop(self) -> None:
        kr = KillRing()
        kr.rotate()
        assert kr.length == 0
        assert kr.peek() is None

    def test_rotate_single_entry_is_noop(self) -> None:
        kr = KillRing()
        kr.push("only", prepend=False)
        kr.rotate()
        assert kr.length == 1
        assert kr.peek() == "only"

    def test_rotate_cycles_through_entries(self) -> None:
        kr = KillRing()
        kr.push("a", prepend=False)
        kr.push("b", prepend=False)
        kr.push("c", prepend=False)
        assert kr.peek() == "c"

        kr.rotate()
        assert kr.peek() == "b"

        kr.rotate()
        assert kr.peek() == "a"

        kr.rotate()
        assert kr.peek() == "c"

    def test_rotate_two_entries(self) -> None:
        kr = KillRing()
        kr.push("x", prepend=False)
        kr.push("y", prepend=False)
        assert kr.peek() == "y"

        kr.rotate()
        assert kr.peek() == "x"

        kr.rotate()
        assert kr.peek() == "y"

    def test_rotate_does_not_change_length(self) -> None:
        kr = KillRing()
        kr.push("a", prepend=False)
        kr.push("b", prepend=False)
        kr.push("c", prepend=False)
        kr.rotate()
        assert kr.length == 3
