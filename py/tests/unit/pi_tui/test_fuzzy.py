"""Tests for pi_tui.fuzzy module."""

from __future__ import annotations

from pi_tui.fuzzy import fuzzy_filter, fuzzy_match

# ---------------------------------------------------------------------------
# fuzzy_match: empty query
# ---------------------------------------------------------------------------


class TestFuzzyMatchEmptyQuery:
    def test_empty_query_always_matches(self) -> None:
        result = fuzzy_match("", "anything")
        assert result.matches is True

    def test_empty_query_score_is_zero(self) -> None:
        result = fuzzy_match("", "hello world")
        assert result.score == 0

    def test_empty_query_against_empty_text(self) -> None:
        result = fuzzy_match("", "")
        assert result.matches is True
        assert result.score == 0


# ---------------------------------------------------------------------------
# fuzzy_match: exact match
# ---------------------------------------------------------------------------


class TestFuzzyMatchExact:
    def test_exact_match(self) -> None:
        result = fuzzy_match("hello", "hello")
        assert result.matches is True

    def test_exact_match_case_insensitive(self) -> None:
        result = fuzzy_match("Hello", "hello")
        assert result.matches is True

    def test_exact_match_at_start_of_longer_text(self) -> None:
        result = fuzzy_match("hello", "hello world")
        assert result.matches is True

    def test_single_char_exact(self) -> None:
        result = fuzzy_match("a", "a")
        assert result.matches is True


# ---------------------------------------------------------------------------
# fuzzy_match: subsequence match
# ---------------------------------------------------------------------------


class TestFuzzyMatchSubsequence:
    def test_subsequence_match(self) -> None:
        result = fuzzy_match("hlo", "hello")
        assert result.matches is True

    def test_subsequence_spread_across_words(self) -> None:
        result = fuzzy_match("hw", "hello world")
        assert result.matches is True

    def test_subsequence_with_gaps(self) -> None:
        result = fuzzy_match("ace", "abcde")
        assert result.matches is True

    def test_subsequence_case_insensitive(self) -> None:
        result = fuzzy_match("HW", "hello world")
        assert result.matches is True


# ---------------------------------------------------------------------------
# fuzzy_match: no match
# ---------------------------------------------------------------------------


class TestFuzzyMatchNoMatch:
    def test_no_match_missing_char(self) -> None:
        result = fuzzy_match("xyz", "hello")
        assert result.matches is False

    def test_no_match_wrong_order(self) -> None:
        result = fuzzy_match("ba", "abc")
        assert result.matches is False

    def test_query_longer_than_text(self) -> None:
        result = fuzzy_match("abcdef", "abc")
        assert result.matches is False

    def test_no_match_score_is_zero(self) -> None:
        result = fuzzy_match("xyz", "hello")
        assert result.score == 0


# ---------------------------------------------------------------------------
# fuzzy_match: scoring
# ---------------------------------------------------------------------------


class TestFuzzyMatchScoring:
    def test_consecutive_matches_score_better_than_spread(self) -> None:
        # "abc" in "abcdef" is fully consecutive
        consecutive = fuzzy_match("abc", "abcdef")
        # "abc" in "a__b__c" has gaps
        spread = fuzzy_match("abc", "a..b..c")
        assert consecutive.matches is True
        assert spread.matches is True
        assert consecutive.score < spread.score

    def test_word_boundary_bonus(self) -> None:
        # Match at word boundary should score better
        boundary = fuzzy_match("w", "hello world")
        non_boundary = fuzzy_match("o", "hello world")
        # 'w' is at a word boundary (after space), 'o' at index 4 is not
        assert boundary.matches is True
        assert non_boundary.matches is True
        # Word boundary gets -10 bonus, so should be lower (better)
        assert boundary.score < non_boundary.score

    def test_match_at_start_gets_boundary_bonus(self) -> None:
        # Position 0 is always a word boundary
        result = fuzzy_match("a", "abcde")
        assert result.matches is True
        # score = -10 (boundary) + 0*0.1 (position) = -10
        assert result.score < 0

    def test_separator_characters_create_word_boundaries(self) -> None:
        # Characters before match: space, dash, underscore, dot, slash, colon
        for sep in [" ", "-", "_", ".", "/", ":"]:
            text = f"x{sep}y"
            result = fuzzy_match("y", text)
            assert result.matches is True
            # 'y' is at a word boundary, should get bonus
            assert result.score < 0, f"Expected word boundary bonus after '{sep}'"

    def test_earlier_match_positions_score_better(self) -> None:
        # Single char match: score includes i * 0.1 position penalty
        early = fuzzy_match("a", "a_____")
        late = fuzzy_match("a", "_____a")
        assert early.matches is True
        assert late.matches is True
        assert early.score < late.score


# ---------------------------------------------------------------------------
# fuzzy_match: alpha-numeric swap fallback
# ---------------------------------------------------------------------------


class TestFuzzyMatchAlphaNumericSwap:
    def test_letters_then_digits_swap(self) -> None:
        # Query "abc123" doesn't match "123abc" directly (wrong order),
        # but the swap fallback tries "123abc" which does match.
        result = fuzzy_match("abc123", "123abc")
        assert result.matches is True

    def test_digits_then_letters_swap(self) -> None:
        # Query "123abc" doesn't match "abc123" directly,
        # swap tries "abc123" which matches.
        result = fuzzy_match("123abc", "abc123")
        assert result.matches is True

    def test_swap_adds_penalty(self) -> None:
        # Swapped match gets +5 penalty compared to direct match
        direct = fuzzy_match("abc123", "abc123")
        swapped = fuzzy_match("123abc", "abc123")
        assert direct.matches is True
        assert swapped.matches is True
        # The swapped score should be the swapped inner score + 5
        assert swapped.score > direct.score

    def test_swap_not_triggered_for_mixed_patterns(self) -> None:
        # "a1b2" is neither pure letters+digits nor digits+letters
        result = fuzzy_match("a1b2", "2b1a")
        assert result.matches is False

    def test_swap_not_triggered_when_primary_matches(self) -> None:
        # If the primary query matches, swap is not used
        result = fuzzy_match("abc", "abc123")
        assert result.matches is True
        # No +5 penalty since primary matched
        # Score should reflect consecutive match bonus
        assert result.score < 5


# ---------------------------------------------------------------------------
# fuzzy_filter: empty query
# ---------------------------------------------------------------------------


class TestFuzzyFilterEmptyQuery:
    def test_empty_query_returns_all(self) -> None:
        items = ["apple", "banana", "cherry"]
        result = fuzzy_filter(items, "", lambda x: x)
        assert result == items

    def test_whitespace_query_returns_all(self) -> None:
        items = ["apple", "banana"]
        result = fuzzy_filter(items, "   ", lambda x: x)
        assert result == items

    def test_empty_items_returns_empty(self) -> None:
        result: list[str] = fuzzy_filter([], "", lambda x: x)
        assert result == []


# ---------------------------------------------------------------------------
# fuzzy_filter: space-separated tokens
# ---------------------------------------------------------------------------


class TestFuzzyFilterTokens:
    def test_single_token(self) -> None:
        items = ["hello world", "goodbye world", "hello there"]
        result = fuzzy_filter(items, "hello", lambda x: x)
        assert len(result) == 2
        assert all("hello" in r.lower() for r in result)

    def test_multiple_tokens_all_must_match(self) -> None:
        items = ["hello world", "goodbye world", "hello there"]
        result = fuzzy_filter(items, "hello world", lambda x: x)
        # Only "hello world" contains both "hello" and "world" as subsequences
        assert len(result) == 1
        assert result[0] == "hello world"

    def test_token_order_irrelevant(self) -> None:
        items = ["hello world"]
        r1 = fuzzy_filter(items, "hello world", lambda x: x)
        r2 = fuzzy_filter(items, "world hello", lambda x: x)
        assert r1 == r2

    def test_partial_token_match_fails(self) -> None:
        items = ["abc"]
        result = fuzzy_filter(items, "abc xyz", lambda x: x)
        # "xyz" doesn't match "abc", so nothing returned
        assert result == []


# ---------------------------------------------------------------------------
# fuzzy_filter: sorting by score
# ---------------------------------------------------------------------------


class TestFuzzyFilterSorting:
    def test_best_match_first(self) -> None:
        items = ["a..b..c", "abc", "aXbXc"]
        result = fuzzy_filter(items, "abc", lambda x: x)
        # "abc" is an exact consecutive match, should be first
        assert result[0] == "abc"

    def test_word_boundary_match_ranked_higher(self) -> None:
        items = ["xyzfoo", "x-foo"]
        result = fuzzy_filter(items, "foo", lambda x: x)
        # "x-foo" has 'f' at a word boundary, should rank better
        assert len(result) == 2
        assert result[0] == "x-foo"

    def test_custom_get_text(self) -> None:
        items = [{"name": "alpha"}, {"name": "beta"}, {"name": "gamma"}]
        result = fuzzy_filter(items, "bet", lambda x: x["name"])
        assert len(result) == 1
        assert result[0]["name"] == "beta"


# ---------------------------------------------------------------------------
# fuzzy_filter: no matches
# ---------------------------------------------------------------------------


class TestFuzzyFilterNoMatches:
    def test_no_matches_returns_empty(self) -> None:
        items = ["apple", "banana", "cherry"]
        result = fuzzy_filter(items, "xyz", lambda x: x)
        assert result == []

    def test_no_matches_with_multiple_tokens(self) -> None:
        items = ["apple", "banana"]
        result = fuzzy_filter(items, "apple xyz", lambda x: x)
        assert result == []
