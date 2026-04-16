from flask import Blueprint, jsonify, request

from devteam_demo.models.book import Book
from devteam_demo.services.search import search_books


bp = Blueprint('books', __name__, url_prefix='/api/books')


@bp.get('')
def list_books():
    term = request.args.get('q', '').strip()
    if term:
        books = search_books(term)
    else:
        books = Book.top_rated(limit=20)
    return jsonify([{'id': b.id, 'title': b.title, 'isbn': b.isbn, 'price_cents': b.price_cents} for b in books])


@bp.get('/<int:book_id>')
def get_book(book_id: int):
    book = Book.find_by_id(book_id) if hasattr(Book, 'find_by_id') else None
    if book is None:
        return jsonify(error='not_found'), 404
    return jsonify({
        'id': book.id,
        'title': book.title,
        'isbn': book.isbn,
        'price_cents': book.price_cents,
        'inventory': book.inventory,
        'description': book.description,
    })
