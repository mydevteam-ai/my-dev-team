from flask import Blueprint, jsonify, request

from devteam_demo.models.review import Review


bp = Blueprint('reviews', __name__, url_prefix='/api/books/<int:book_id>/reviews')


@bp.get('')
def list_reviews(book_id: int):
    reviews = Review.for_book(book_id) if hasattr(Review, 'for_book') else []
    return jsonify([{'id': r.id, 'rating': r.rating, 'body': r.body} for r in reviews])


@bp.post('')
def create_review(book_id: int):
    payload = request.get_json() or {}
    review = Review(
        book_id=book_id,
        user_id=payload['user_id'],
        rating=int(payload['rating']),
        body=payload.get('body', ''),
    )
    review.save() if hasattr(review, 'save') else None
    return jsonify(id=review.id), 201
