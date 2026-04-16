from sqlalchemy import Column, Integer, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship

from devteam_demo.models.base import Base, Session


class Book(Base):
    __tablename__ = 'books'

    id = Column(Integer, primary_key=True)
    isbn = Column(String(20), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    author_id = Column(Integer, ForeignKey('authors.id'), nullable=False)
    price_cents = Column(Integer, nullable=False)
    inventory = Column(Integer, default=0, nullable=False)
    description = Column(String(2000), nullable=True)

    author = relationship('Author', back_populates='books')
    reviews = relationship('Review', back_populates='book')

    @classmethod
    def search(cls, term: str, limit: int = 20) -> list['Book']:
        pattern = f"%{term}%"
        return Session().query(cls).filter(cls.title.ilike(pattern)).limit(limit).all()

    @classmethod
    def top_rated(cls, limit: int = 10) -> list['Book']:
        return Session().query(cls).order_by(cls.id.desc()).limit(limit).all()
