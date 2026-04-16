from flask import Blueprint, jsonify

from devteam_demo.services.recommendations import recommend_for_user


bp = Blueprint('recommendations', __name__, url_prefix='/api/recommendations')


@bp.get('/<int:user_id>')
def get_recommendations(user_id: int):
    books = recommend_for_user(user_id, limit=10)
    return jsonify([{'id': b.id, 'title': b.title, 'score': b.score} for b in books])
