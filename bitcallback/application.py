"""bitcallback.py

Create and initialize flask app and async tasks
"""
import atexit
import tempfile

from flask import Flask
from bitcallback.bitmon_task import BitmonTask
from bitcallback.callback_task import CallbackTask

from bitcallback.models import db



def init_app(app):
    """
    Initialize flask app database and create tasks.

    Arguments:
        app: Uninitialized flask app with loaded configuration

    Returns:
        initialized flask app
    """
    # Initialize and start bitcoin and callback processes
    app.callback_task = CallbackTask(app.config)
    app.bitmon_task = BitmonTask(app.callback_task, app.config)

    # Don't initialize db until task are created so the session isn't shared
    db.init_app(app)

    with app.app_context():
        db.create_all()

    def clean_up():
        """Send termination command to other tasks and wait until they exit"""
        # The order in which the tasks are closed is important, because
        # bitmon_task can send command to callback_task
        app.bitmon_task.close()
        app.callback_task.close()

    # When a kill (SIGTERM) signal is received close gracefully
    atexit.register(clean_up)

    return app



def create_db():
    # Create all database tables
    db.create_all()
