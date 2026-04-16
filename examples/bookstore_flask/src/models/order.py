from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from devteam_demo.models.base import Base, Session


class Order(Base):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    status = Column(String(32), default='pending', nullable=False)
    total_cents = Column(Integer, nullable=False)
    placed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    shipping_address = Column(String(500), nullable=True)

    items = relationship('OrderItem', back_populates='order', cascade='all, delete-orphan')

    def mark_paid(self) -> None:
        self.status = 'paid'
        Session().commit()

    def mark_shipped(self, tracking_number: str) -> None:
        self.status = 'shipped'
        self.shipping_address = tracking_number
        Session().commit()


class OrderItem(Base):
    __tablename__ = 'order_items'

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    book_id = Column(Integer, ForeignKey('books.id'), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price_cents = Column(Integer, nullable=False)

    order = relationship('Order', back_populates='items')
