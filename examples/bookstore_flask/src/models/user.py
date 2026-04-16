from sqlalchemy import Column, Integer, String, Boolean

from devteam_demo.models.base import Base, Session


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    two_factor_secret = Column(String(32), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    @classmethod
    def find_by_username(cls, username: str) -> 'User | None':
        return Session().query(cls).filter_by(username=username).first()

    @classmethod
    def find_by_id(cls, user_id: int) -> 'User | None':
        return Session().query(cls).get(user_id)

    def save(self) -> None:
        session = Session()
        session.add(self)
        session.commit()
