# Import SQLAlchemy
import logging
import multiprocessing_logging

from bitcallback.application import create_app
from bitcallback.logger import LOGGING_FORMAT

print("WHYYYYYYYYYYYYYYYYYYY")

# Initialize logging
#logging.basicConfig(filename='error.log', format=LOGGING_FORMAT, level=logging.DEBUG)

logging.basicConfig(format=LOGGING_FORMAT, level=logging.DEBUG)
multiprocessing_logging.install_mp_handler()


# Defime WSGI application object
app  = create_app(__name__, 'config')

# Automatically close session at the end of the request or
# when the application shuts down
#@app.teardown_appcontext
#def shutdown_session(exception=None):
#    db_session.remove()


# Import API views
import bitcallback.views
