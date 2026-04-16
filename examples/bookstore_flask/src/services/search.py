from devteam_demo.models.book import Book


def search_books(term: str, limit: int = 20) -> list[Book]:
    """Fuzzy-search books by title or ISBN."""
    term = term.strip()
    if not term:
        return []
    return Book.search(term, limit=limit)


def suggest_titles(prefix: str, limit: int = 5) -> list[str]:
    """Return a short list of title completions for an autocomplete box."""
    books = Book.search(prefix, limit=limit)
    return [b.title for b in books]
