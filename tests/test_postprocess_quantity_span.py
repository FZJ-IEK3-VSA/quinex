import pytest
from quinex.extract.subtasks.quantity_span_identification import postprocess_quantity_span



# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def assert_quantity_span_postproc(quantity_text, expected_text, full_text=None, quantity_start_char=0):
    """Postprocess quantity_text, assert resulting text matches expected_text, and offsets are consistent."""
    if full_text is None:
        # `full_text` can default to text as it is only relevant when characters surrounding
        # the span matter (e.g., when testing appending % or closing parenthesis).        
        full_text = quantity_text

    quantity_span = {"text": quantity_text, "start": quantity_start_char, "end": quantity_start_char + len(quantity_text)}
    pp_result = postprocess_quantity_span(quantity_span, full_text)

    assert pp_result["text"] == expected_text
    assert pp_result["start"] <= pp_result["end"]
    assert full_text[pp_result["start"] : pp_result["end"]] == expected_text


# ---------------------------------------------------------------------------
# Leading and trailing garbage chars
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("leading_chars", [")", "]", "}"])
def test_leading_garbage_chars_removed(leading_chars):
    assert_quantity_span_postproc(leading_chars + "42 kg", "42 kg")

@pytest.mark.parametrize("trailing_chars", [",", ";", ":", "(", ",;", ")."])
def test_trailing_garbage_chars_removed(trailing_chars):
    assert_quantity_span_postproc("42 kg" + trailing_chars, "42 kg")
    assert_quantity_span_postproc("50%" + trailing_chars, "50%")


# ---------------------------------------------------------------------------
# Unmatched parentheses
# ---------------------------------------------------------------------------

def test_balanced_parentheses_stripped():
    assert_quantity_span_postproc("(42 kg)", "42 kg")
    assert_quantity_span_postproc("((42 kg))", "42 kg")

def test_unmatched_leading_parenthesis_removed():
    assert_quantity_span_postproc("(42 kg", "42 kg")
    assert_quantity_span_postproc("((42 kg)", "42 kg")

def test_unmatched_trailing_parenthesis_removed():
    assert_quantity_span_postproc("42 kg)", "42 kg")
    assert_quantity_span_postproc("42 (kg))", "42 (kg)")

def test_balanced_leading_and_trailing_parenthesis_not_stripped():
    assert_quantity_span_postproc("42 (kg)", "42 (kg)")
    assert_quantity_span_postproc("(42) kg", "(42) kg")


# ---------------------------------------------------------------------------
# Whitespace trimming
# ---------------------------------------------------------------------------

def test_leading_whitespace_trimmed():
    assert_quantity_span_postproc("  42 kg", "42 kg")

def test_trailing_whitespace_trimmed():
    assert_quantity_span_postproc("42 kg  ", "42 kg")

def test_both_ends_whitespace_trimmed():
    assert_quantity_span_postproc("  42 kg  ", "42 kg")

def test_both_ends_whitespace_trimmed_after_edits():
    assert_quantity_span_postproc("  42 kg )  ", "42 kg")


# ---------------------------------------------------------------------------
# Percent sign appended from following character in full_text
# ---------------------------------------------------------------------------

def test_percent_appended_when_immediately_follows():
    assert_quantity_span_postproc("70", "70%", "the efficiency is 70% for", 18)

def test_percent_not_appended_when_not_adjacent():
    assert_quantity_span_postproc("10", "10", "10 and 20%")


# ---------------------------------------------------------------------------
# Parenthesis closed from following character in full_text
# ---------------------------------------------------------------------------
PARENTHESES = [("(", ")"), ("[", "]"), ("{", "}")]
@pytest.mark.parametrize("o, c", PARENTHESES)
def test_closing_parenthesis_absorbed_from_full_text(o, c):
    assert_quantity_span_postproc(f"42 {o}kg", f"42 {o}kg{c}", f"42 {o}kg{c} something")

@pytest.mark.parametrize("o, c", PARENTHESES)
def test_closing_parenthesis_not_absorbed_if_surrounding(o, c):
    assert_quantity_span_postproc(f"{o}42 kg", f"42 kg", f"{o}42 kg{c} something")

@pytest.mark.parametrize("o, c", PARENTHESES)
def test_closing_parenthesis_not_absorbed_when_already_balanced(o, c):
    assert_quantity_span_postproc(f"{o}10-20{c}", "10-20", f"range {o}10-20{c} kg", 6)


# ---------------------------------------------------------------------------
# Idempotent cases
# ---------------------------------------------------------------------------

def test_already_clean_span_unchanged():
    assert_quantity_span_postproc("42 kg", "42 kg")
    assert_quantity_span_postproc("99.5%", "99.5%")

def test_empty_span_unchanged():
    assert_quantity_span_postproc("", "")
