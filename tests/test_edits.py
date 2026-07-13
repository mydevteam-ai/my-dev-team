import pytest
from devteam.utils.edits import EditError, apply_edits


class TestApplyEdits:
    def test_unique_replace(self):
        text = 'const a = 1;\nconst b = 2;\n'
        result = apply_edits(text, 'a.ts', [('const a = 1;', 'const a = 42;')])
        assert result == 'const a = 42;\nconst b = 2;\n'

    def test_replacement_is_literal(self):
        # Regex-looking replacement text must be inserted verbatim.
        result = apply_edits('const re = OLD;', 'a.ts', [('OLD', "'$&-\\1'")])
        assert result == "const re = '$&-\\1';"

    def test_not_found_message(self):
        with pytest.raises(EditError, match=r"old_text was not found in a\.py"):
            apply_edits('const a = 1;', 'a.py', [('const b = 2;', 'x')])

    def test_not_found_mentions_reading_the_file(self):
        with pytest.raises(EditError, match='copy the text to replace exactly'):
            apply_edits('x', 'a.py', [('y', 'z')])

    def test_ambiguous_match_reports_count(self):
        text = 'let x = 0;\nlet x = 0;\nlet x = 0;'
        with pytest.raises(EditError, match=r"matches 3 places in a\.py.*surrounding"):
            apply_edits(text, 'a.py', [('let x = 0;', 'let y = 0;')])

    def test_identical_old_and_new(self):
        with pytest.raises(EditError, match='identical; nothing to change'):
            apply_edits('const a = 1;', 'a.py', [('const a = 1;', 'const a = 1;')])

    def test_lf_snippet_matches_crlf_file(self):
        text = 'one\r\ntwo\r\nthree\r\n'
        result = apply_edits(text, 'a.txt', [('one\ntwo', 'uno\ndos')])
        # Replacement is re-stamped to CRLF; untouched tail keeps its CRLF.
        assert result == 'uno\r\ndos\r\nthree\r\n'

    def test_crlf_snippet_matches_lf_file(self):
        text = 'one\ntwo\nthree\n'
        result = apply_edits(text, 'a.txt', [('one\r\ntwo', 'uno\r\ndos')])
        assert result == 'uno\ndos\nthree\n'

    def test_escaped_newline_snippet_matches_real_newlines(self):
        # The double-escaped-newline salvage that WorkspaceFile.content gets
        # also rescues an edit whose snippet arrived with literal backslash-n.
        text = 'import a\n\nimport b\n'
        result = apply_edits(text, 'a.py', [('import a\\n\\nimport b', 'import a\\n\\nimport c')])
        assert result == 'import a\n\nimport c\n'

    def test_raw_match_wins_over_normalization(self):
        # A snippet with a legitimate literal backslash-n matches raw first.
        text = 'sep = "\\n"\n'
        result = apply_edits(text, 'a.py', [('sep = "\\n"', 'sep = "\\t"')])
        assert result == 'sep = "\\t"\n'

    def test_edits_apply_in_order(self):
        text = 'a = 1\nb = 2\n'
        result = apply_edits(text, 'a.py', [('a = 1', 'a = 10'), ('a = 10\nb = 2', 'a = 10\nb = 20')])
        assert result == 'a = 10\nb = 20\n'

    def test_error_carries_failing_edit_index(self):
        with pytest.raises(EditError) as exc_info:
            apply_edits('a = 1\n', 'a.py', [('a = 1', 'a = 2'), ('missing', 'x')])
        assert exc_info.value.index == 1

    def test_only_first_occurrence_replaced_after_uniqueness(self):
        # An edit may create text that a later old_text matches uniquely.
        text = 'x = 1\ny = 1\n'
        result = apply_edits(text, 'a.py', [('x = 1', 'y = 2')])
        assert result == 'y = 2\ny = 1\n'
