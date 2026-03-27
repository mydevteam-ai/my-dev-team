def normalize_status(value: str) -> str:
    if not value:
        return ''
    return value.strip().strip('.').upper()

def is_approved(value: str) -> bool:
    return normalize_status(value) in {'APPROVED', 'PASSED'}
