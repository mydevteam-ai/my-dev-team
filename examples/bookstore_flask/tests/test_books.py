from devteam_demo.services.search import search_books, suggest_titles


def test_search_books_returns_results(monkeypatch, fake_book):
    monkeypatch.setattr('devteam_demo.models.book.Book.search', lambda term, limit=20: [fake_book])
    results = search_books('python')
    assert results == [fake_book]


def test_search_books_empty_term(monkeypatch):
    called = False
    def fake_search(*_, **__):
        nonlocal called
        called = True
        return []
    monkeypatch.setattr('devteam_demo.models.book.Book.search', fake_search)
    assert search_books('   ') == []
    assert called is False


def test_suggest_titles(monkeypatch, fake_book):
    monkeypatch.setattr('devteam_demo.models.book.Book.search', lambda term, limit=5: [fake_book])
    assert suggest_titles('py') == [fake_book.title]
