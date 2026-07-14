"""Exact old_text/new_text replacement for edit-based code submission.

Mirrors my-dev-team-vs-code's `edit` tool semantics: an edit's `old_text`
must match exactly one place in the file, line endings are bridged so an
LF snippet still matches a CRLF file (and vice versa), and every failure
carries a model-facing message that tells the agent how to correct the
call.
"""
from .sanitizer import normalize_workspace_content


class EditError(ValueError):
    """A failed or ambiguous edit match. The message is model-facing repair feedback."""

    def __init__(self, index: int, message: str):
        super().__init__(message)
        self.index = index


def _match_line_endings(file_text: str, snippet: str) -> str:
    """Re-stamp a snippet with the file's line-ending style.

    The snippet is converted instead of the file, so an edit never rewrites
    the file's own line endings as a side effect.
    """
    lf = snippet.replace('\r\n', '\n')
    return lf.replace('\n', '\r\n') if '\r\n' in file_text else lf


def apply_edits(text: str, path: str, edits: list[tuple[str, str]]) -> str:
    """Apply (old_text, new_text) replacements in order; each must match exactly once.

    Candidate needles are tried per edit: the raw old_text, then the
    line-ending-bridged form, then the escape-normalized form (the same
    double-escaped-newline salvage `WorkspaceFile.content` gets). Whichever
    matches, new_text receives the same transforms so mixed line endings or
    stray escapes never leak into the file.
    """
    for index, (old_text, new_text) in enumerate(edits):
        if old_text == new_text:
            raise EditError(index, "old_text and new_text are identical; nothing to change.")
        candidates = [(old_text, new_text)]
        candidates.append((_match_line_endings(text, old_text), _match_line_endings(text, new_text)))
        normalized = normalize_workspace_content(old_text)
        if normalized != old_text:
            candidates.append((
                _match_line_endings(text, normalized),
                _match_line_endings(text, normalize_workspace_content(new_text)),
            ))
        needle, replacement = next(
            ((old, new) for old, new in candidates if old in text), candidates[-1]
        )
        count = text.count(needle)
        if count == 0:
            raise EditError(index, (
                f"old_text was not found in {path}. Read the file and copy the text "
                "to replace exactly, including whitespace and indentation."
            ))
        if count > 1:
            raise EditError(index, (
                f"old_text matches {count} places in {path}. Include more surrounding "
                "lines so it matches exactly one place."
            ))
        text = text.replace(needle, replacement, 1)
    return text
