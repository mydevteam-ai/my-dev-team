from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from devteam_demo.models.base import Base, Session


class Author(Base):
    __tablename__ = 'authors'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    bio = Column(String(4000), nullable=True)
    country = Column(String(64), nullable=True)

    books = relationship('Book', back_populates='author')

    @classmethod
    def find_by_name(cls, name: str) -> 'Author | None':
        return Session().query(cls).filter_by(name=name).first()
