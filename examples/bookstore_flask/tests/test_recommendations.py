from unittest.mock import MagicMock

from devteam_demo.services.recommendations import recommend_for_user


def test_recommend_falls_back_to_top_rated(monkeypatch):
    monkeypatch.setattr('devteam_demo.models.order.Order.for_user', lambda user_id: [], raising=False)
    monkeypatch.setattr('devteam_demo.models.book.Book.top_rated', lambda limit=10: ['top1', 'top2'])
    assert recommend_for_user(42) == ['top1', 'top2']


def test_recommend_filters_by_author(monkeypatch):
    fake_book = MagicMock(author_id=7)
    fake_item = MagicMock(book=fake_book)
    fake_order = MagicMock(items=[fake_item])
    monkeypatch.setattr('devteam_demo.models.order.Order.for_user', lambda user_id: [fake_order], raising=False)
    candidates = [MagicMock(author_id=7), MagicMock(author_id=8), MagicMock(author_id=7)]
    monkeypatch.setattr('devteam_demo.models.book.Book.top_rated', lambda limit=30: candidates)
    result = recommend_for_user(1, limit=2)
    assert all(b.author_id == 7 for b in result)
