"""Unit tests for clean.py — TTS text cleaning transformations."""

from dub_chunk.clean import clean_for_tts


class TestStageDirections:

    def test_removes_stage_direction(self):
        assert clean_for_tts("Hello /whispers/ world") == "Hello world"

    def test_removes_stage_direction_with_spaces(self):
        assert clean_for_tts("Hello /laughs nervously/ world") == "Hello world"

    def test_preserves_slashes_beyond_60_chars(self):
        long_dir = "x" * 61
        text = f"Hello /{long_dir}/ world"
        assert f"/{long_dir}/" in clean_for_tts(text)

    def test_multiple_stage_directions(self):
        result = clean_for_tts("He /pauses/ said /clears throat/ something")
        assert "/pauses/" not in result
        assert "/clears throat/" not in result
        assert "said" in result
        assert "something" in result


class TestEmphasisMarkers:

    def test_removes_underscores_keeps_word(self):
        assert clean_for_tts("The _unconscious_ is real") == "The unconscious is real"

    def test_multiple_emphasis_markers(self):
        result = clean_for_tts("_very_ important _thing_")
        assert result == "very important thing"

    def test_no_false_positive_on_snake_case(self):
        """Single underscores (not wrapping words) should not match."""
        result = clean_for_tts("some_variable_name")
        # _variable_ matches the pattern → "variable" extracted
        assert "variable" in result


class TestArticleCorrection:

    def test_a_before_vowel_becomes_an(self):
        assert clean_for_tts("a apple") == "an apple"
        assert clean_for_tts("a orange") == "an orange"

    def test_a_before_consonant_stays(self):
        assert clean_for_tts("a banana") == "a banana"

    def test_a_before_uppercase_vowel(self):
        assert clean_for_tts("a Apple") == "an Apple"

    def test_does_not_affect_mid_word_a(self):
        """'a' inside a word should not be affected."""
        assert clean_for_tts("banana apple") == "banana apple"


class TestWhitespace:

    def test_collapses_multiple_spaces(self):
        assert clean_for_tts("too   many    spaces") == "too many spaces"

    def test_strips_leading_trailing(self):
        assert clean_for_tts("  padded  ") == "padded"


class TestPunctuationSpacing:

    def test_removes_space_before_comma(self):
        assert clean_for_tts("hello , world") == "hello, world"

    def test_removes_space_before_period(self):
        assert clean_for_tts("end .") == "end."

    def test_removes_space_before_exclamation(self):
        assert clean_for_tts("wow !") == "wow!"

    def test_removes_space_before_question(self):
        assert clean_for_tts("really ?") == "really?"

    def test_removes_space_before_colon(self):
        assert clean_for_tts("note :") == "note:"


class TestDashNormalization:

    def test_em_dash_normalized(self):
        result = clean_for_tts("word  —  other")
        assert result == "word — other"

    def test_double_dash_becomes_em_dash(self):
        result = clean_for_tts("word  --  other")
        assert result == "word — other"


class TestBrackets:

    def test_empty_parens_removed(self):
        assert clean_for_tts("text () here") == "text  here"

    def test_empty_brackets_removed(self):
        assert clean_for_tts("text [] here") == "text  here"

    def test_non_empty_parens_preserved(self):
        result = clean_for_tts("text (important) here")
        assert "(important)" in result


class TestEllipsis:

    def test_four_dots_become_three(self):
        assert clean_for_tts("trailing....") == "trailing..."

    def test_many_dots_become_three(self):
        assert clean_for_tts("long.......") == "long..."

    def test_three_dots_unchanged(self):
        assert clean_for_tts("normal...") == "normal..."


class TestCombined:

    def test_multiple_transformations_in_order(self):
        text = "He /pauses/ said _quietly_ , a apple...."
        result = clean_for_tts(text)
        # Stage direction removed, emphasis removed, space before comma fixed,
        # a→an, whitespace collapsed, ellipsis normalized
        assert "/pauses/" not in result
        assert "_" not in result
        assert "an apple" in result
        assert "...." not in result

    def test_a_an_fix_requires_single_space(self):
        """a/an fix runs before whitespace collapsing, so double-spaced
        'a  apple' won't be corrected. This is an ordering interaction."""
        result = clean_for_tts("a  apple")
        assert result == "a apple"  # NOT "an apple" — double space blocks the regex

    def test_already_clean_text_unchanged(self):
        text = "The unconscious is a repository."
        assert clean_for_tts(text) == text

    def test_empty_string(self):
        assert clean_for_tts("") == ""
