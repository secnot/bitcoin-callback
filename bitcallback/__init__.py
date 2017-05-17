# Import SQLAlchemy
import logging
import multiprocessing_logging
from flask import Flask

from bitcallback.application import init_app
from bitcallback.logger import LOGGING_FORMAT, LOGGING_FORMAT_SHORT

# Initialize logging
#logging.basicConfig(filename='error.log', format=LOGGING_FORMAT, level=logging.DEBUG)

logging.basicConfig(format=LOGGING_FORMAT_SHORT, level=logging.DEBUG)

# This allows several processes to send logs
multiprocessing_logging.install_mp_handler()


# Defime WSGI application object
app = Flask(__name__)
app.config.from_object('bitcallback.config')
init_app(app)

# Automatically close session at the end of the request or
# when the application shuts down
#@app.teardown_appcontext
#def shutdown_session(exception=None):
#    db_session.remove()


# Import API views
import bitcallback.views
