from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from devteam_demo.models.base import Base, Session


class Review(Base):
    __tablename__ = 'reviews'

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey('books.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    rating = Column(Integer, nullable=False)
    body = Column(String(4000), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    book = relationship('Book', back_populates='reviews')

    @classmethod
    def average_rating_for_book(cls, book_id: int) -> float:
        reviews = Session().query(cls).filter_by(book_id=book_id).all()
        if not reviews:
            return 0.0
        return sum(r.rating for r in reviews) / len(reviews)
