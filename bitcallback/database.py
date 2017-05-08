"""
database.py

Tasks DB session initialization and related functions.
"""
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

@contextmanager
def make_session_scope(db_session):
    """Provide a transactional scope around a series of operations."""
    session = db_session()
    session.expire_on_commit = False
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


def configure_db(db_uri=None):
    # Create a new db session for the process
    engine = create_engine(db_uri)

    db_session = scoped_session(sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine))

    return db_session


