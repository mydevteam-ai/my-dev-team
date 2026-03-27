import re

def normalize_workspace_content(text: str) -> str:
    """Normalize double-escaped newlines from LLM JSON responses."""
    escaped_nl = text.count('\\n')
    escaped_crlf = text.count('\\r\\n')
    if escaped_nl == 0 and escaped_crlf == 0:
        return text
    real_nl = text.count('\n')
    should_normalize = real_nl == 0 and (escaped_nl > 0 or escaped_crlf > 0)
    if not should_normalize and ('\\n\\n' in text or '\\r\\n\\r\\n' in text):
        should_normalize = True
    if not should_normalize and escaped_nl >= 4 and escaped_nl > (real_nl * 2):
        should_normalize = True
    if not should_normalize:
        return text
    return text.replace('\\r\\n', '\n').replace('\\n', '\n')

def sanitize_for_prompt(content: str, protected_tags: str | list[str] = None) -> str:
    """
    Cleans raw file content and text before injecting it into an LLM prompt.
    """
    if not content:
        return ''
    safe_content = content
    if protected_tags:
        if isinstance(protected_tags, str):
            protected_tags = [protected_tags]
        for tag in protected_tags:
            closing_tag = f'</{tag}>'
            safe_closing = f'&lt;/{tag}&gt;'
            safe_content = safe_content.replace(closing_tag, safe_closing)
    safe_content = re.sub(
        r'data:image\/[^;]+;base64,[a-zA-Z0-9+/]+=*',
        '[BASE64_DATA_REMOVED_TO_SAVE_TOKENS]',
        safe_content
    )
    safe_content = re.sub(r'\n{3,}', '\n\n', safe_content)
    safe_content = safe_content.replace('\x00', '')
    return safe_content.strip()
