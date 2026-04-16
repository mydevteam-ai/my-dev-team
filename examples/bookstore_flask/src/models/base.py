from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker
from sqlalchemy import create_engine


_engine = create_engine('sqlite:///bookstore.db', future=True)
Session = scoped_session(sessionmaker(bind=_engine, future=True))
Base = declarative_base()
