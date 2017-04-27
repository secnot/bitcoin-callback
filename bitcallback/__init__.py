from flask import Flask

# Import SQLAlchemy
from .bitcallback import create_app


print("WHYYYYYYYYYYYYYYYYYYY")
# Defime WSGI application object
app, bitmon_q, callback_q  = create_app(__name__)

from bitcallback.database import db_session, init_db
# Automatically close session at the end of the request or
# when the application shuts down
@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

# Initialize database
init_db()

# Import API views
import bitcallback.views
