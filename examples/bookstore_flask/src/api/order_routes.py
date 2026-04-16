from flask import Blueprint, jsonify, request

from devteam_demo.models.order import Order, OrderItem
from devteam_demo.services.payment import charge_card


bp = Blueprint('orders', __name__, url_prefix='/api/orders')


@bp.post('')
def place_order():
    payload = request.get_json() or {}
    items = payload.get('items', [])
    total = sum(int(i['unit_price_cents']) * int(i['quantity']) for i in items)
    order = Order(user_id=payload['user_id'], total_cents=total)
    order.items = [
        OrderItem(book_id=i['book_id'], quantity=i['quantity'], unit_price_cents=i['unit_price_cents'])
        for i in items
    ]
    order.save() if hasattr(order, 'save') else None
    charge_card(payload['card_token'], total)
    order.mark_paid()
    return jsonify(order_id=order.id, status=order.status), 201


@bp.get('/<int:order_id>')
def get_order(order_id: int):
    order = Order.find_by_id(order_id) if hasattr(Order, 'find_by_id') else None
    if order is None:
        return jsonify(error='not_found'), 404
    return jsonify({'id': order.id, 'status': order.status, 'total_cents': order.total_cents})
