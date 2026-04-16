from devteam_demo.models.book import Book
from devteam_demo.models.order import Order


def recommend_for_user(user_id: int, limit: int = 10) -> list[Book]:
    """Return a personalised list of book recommendations for a user.

    Naive heuristic: look at books the user has already ordered, collect the
    set of authors, then return other best-selling titles from those authors.
    """
    past_orders = Order.for_user(user_id) if hasattr(Order, 'for_user') else []
    seen_author_ids = {item.book.author_id for order in past_orders for item in order.items}
    if not seen_author_ids:
        return Book.top_rated(limit=limit)
    return [b for b in Book.top_rated(limit=limit * 3) if b.author_id in seen_author_ids][:limit]
