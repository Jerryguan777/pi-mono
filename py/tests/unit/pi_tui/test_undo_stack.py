"""Tests for UndoStack."""

from dataclasses import dataclass, field

from pi_tui.undo_stack import UndoStack


class TestUndoStackInitialState:
    def test_empty_stack_has_length_zero(self) -> None:
        stack: UndoStack[int] = UndoStack()
        assert stack.length == 0

    def test_pop_on_empty_returns_none(self) -> None:
        stack: UndoStack[str] = UndoStack()
        assert stack.pop() is None

    def test_pop_on_empty_keeps_length_zero(self) -> None:
        stack: UndoStack[int] = UndoStack()
        stack.pop()
        assert stack.length == 0


class TestPushAndPop:
    def test_push_increments_length(self) -> None:
        stack: UndoStack[int] = UndoStack()
        stack.push(1)
        assert stack.length == 1
        stack.push(2)
        assert stack.length == 2

    def test_pop_decrements_length(self) -> None:
        stack: UndoStack[int] = UndoStack()
        stack.push(10)
        stack.push(20)
        stack.pop()
        assert stack.length == 1

    def test_lifo_order(self) -> None:
        stack: UndoStack[str] = UndoStack()
        stack.push("a")
        stack.push("b")
        stack.push("c")
        assert stack.pop() == "c"
        assert stack.pop() == "b"
        assert stack.pop() == "a"

    def test_pop_after_exhaustion_returns_none(self) -> None:
        stack: UndoStack[int] = UndoStack()
        stack.push(1)
        stack.pop()
        assert stack.pop() is None


class TestDeepCopySemantics:
    def test_modifying_original_after_push_does_not_affect_stored(self) -> None:
        data = [1, 2, 3]
        stack: UndoStack[list[int]] = UndoStack()
        stack.push(data)
        data.append(4)
        popped = stack.pop()
        assert popped == [1, 2, 3]

    def test_nested_object_is_deep_copied(self) -> None:
        @dataclass
        class State:
            items: list[str] = field(default_factory=list)

        state = State(items=["x"])
        stack: UndoStack[State] = UndoStack()
        stack.push(state)
        state.items.append("y")
        popped = stack.pop()
        assert popped is not None
        assert popped.items == ["x"]

    def test_dict_is_deep_copied(self) -> None:
        data = {"nested": {"key": "value"}}
        stack: UndoStack[dict[str, dict[str, str]]] = UndoStack()
        stack.push(data)
        data["nested"]["key"] = "changed"
        popped = stack.pop()
        assert popped is not None
        assert popped["nested"]["key"] == "value"


class TestPoppedValueIsDetached:
    def test_modifying_popped_value_does_not_affect_stack(self) -> None:
        stack: UndoStack[list[int]] = UndoStack()
        stack.push([1, 2])
        stack.push([3, 4])
        popped = stack.pop()
        assert popped is not None
        popped.append(5)
        # The remaining item in the stack should be unaffected
        remaining = stack.pop()
        assert remaining == [1, 2]

    def test_popped_dataclass_is_independent(self) -> None:
        @dataclass
        class Config:
            value: int = 0

        stack: UndoStack[Config] = UndoStack()
        stack.push(Config(value=10))
        stack.push(Config(value=20))
        first_pop = stack.pop()
        assert first_pop is not None
        first_pop.value = 999
        second_pop = stack.pop()
        assert second_pop is not None
        assert second_pop.value == 10


class TestClear:
    def test_clear_removes_all_snapshots(self) -> None:
        stack: UndoStack[int] = UndoStack()
        stack.push(1)
        stack.push(2)
        stack.push(3)
        stack.clear()
        assert stack.length == 0
        assert stack.pop() is None

    def test_clear_on_empty_stack_is_noop(self) -> None:
        stack: UndoStack[int] = UndoStack()
        stack.clear()
        assert stack.length == 0

    def test_push_after_clear_works(self) -> None:
        stack: UndoStack[str] = UndoStack()
        stack.push("a")
        stack.push("b")
        stack.clear()
        stack.push("c")
        assert stack.length == 1
        assert stack.pop() == "c"


class TestMultiplePushPopSequences:
    def test_interleaved_push_pop(self) -> None:
        stack: UndoStack[int] = UndoStack()
        stack.push(1)
        stack.push(2)
        assert stack.pop() == 2
        stack.push(3)
        assert stack.pop() == 3
        assert stack.pop() == 1
        assert stack.pop() is None

    def test_length_tracks_through_mixed_operations(self) -> None:
        stack: UndoStack[int] = UndoStack()
        assert stack.length == 0
        stack.push(10)
        assert stack.length == 1
        stack.push(20)
        assert stack.length == 2
        stack.pop()
        assert stack.length == 1
        stack.push(30)
        stack.push(40)
        assert stack.length == 3
        stack.clear()
        assert stack.length == 0
        stack.push(50)
        assert stack.length == 1

    def test_repeated_push_pop_of_same_value(self) -> None:
        stack: UndoStack[list[int]] = UndoStack()
        data = [1, 2, 3]
        stack.push(data)
        stack.push(data)
        first = stack.pop()
        second = stack.pop()
        # Both are equal but independent copies
        assert first == second
        assert first is not second
