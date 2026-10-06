import pytest

from memoria.lancedb_manager import emotion_where_clause, sql_string_literal


def test_sql_string_literal_escapes_single_quotes():
    assert sql_string_literal("o'brien") == "'o''brien'"


def test_sql_string_literal_neutralizes_injection():
    assert sql_string_literal("x' OR '1'='1") == "'x'' OR ''1''=''1'"


@pytest.mark.parametrize("value", [None, "", "neutral"])
def test_emotion_where_clause_skips_empty_and_neutral(value):
    assert emotion_where_clause(value) is None


def test_emotion_where_clause_builds_like_filter():
    assert emotion_where_clause("alegría") == "metadata LIKE '%alegría%'"


@pytest.mark.parametrize("value", ["x' OR '1'='1", "100%", "dos palabras"])
def test_emotion_where_clause_rejects_non_word_values(value):
    assert emotion_where_clause(value) is None
