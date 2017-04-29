"""
database:

Database creation and configuration functions
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from bitcallback.query import PaginatedQuery

engine = create_engine('sqlite:////home/secnot/bitcoin-callback/app.db')

db_session = scoped_session(sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    query_cls=PaginatedQuery))

Base = declarative_base()
Base.query = db_session.query_property()
Base.session = db_session

def init_db():
    """
    import all modules here that might define models so that
    they will be registered properly on the metadata.  Otherwise
    you will have to import them first before calling init_db()
    """
    import bitcallback.models
    Base.metadata.create_all(bind=engine)

