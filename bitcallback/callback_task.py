import threading
from multiprocessing import Process, Queue
from datetime import datetime, timedelta
import collections
import logging
import pickle
import requests
import queue
import json

from bitcallback.models import Callback, Subscription
from bitcallback.commands import (NEW_CALLBACK, ACK_CALLBACK, EXIT_TASK)
from bitcallback.database import make_session_scope, configure_db
from bitcallback.thread_pool import ThreadPool


CALLBACK_REQUEST_TIMEOUT = 1 # In seconds


CallbackRecord = collections.namedtuple('CallbackRecord', ['id', 'retries', 'last_retry'])

logger = logging.getLogger("Callback")


class CallbackManager(object):

    def __init__(self,
                 db_session,
                 retries=3, retry_period=120,
                 nthreads=10, recover_db=True):
        # Dictionary containing all callback indexed by (txid, addr)
        self._callbacks = {}

        # Queue of callbacks ids to retry ordered by last retry time
        self._retry_q = collections.deque()

        # SQLAlchemy session
        self._db_session = db_session

        # Queue where ThreadPool threads stores the ids of sent callbacks
        self._sent_q = queue.Queue()

        # Lock for every thing excepts DB access
        self._lock = threading.Lock()

        # DB access lock
        self._db_lock = threading.Lock()

        # Max number of callback retries
        self.retries = retries

        # Wait between sucessive unacknowledged callback tries
        self.retry_period = retry_period

        # Start request thread pool
        self._thread_pool = ThreadPool(
            nthreads=nthreads,
            func=CallbackManager._send_thread_func,
            args=(self._sent_q,))

        # Flag used to notify update_thread to stop
        self._close_flag = threading.Event()

        # Start update thread
        self._update_thread = threading.Thread(
            target=CallbackManager._update_func,
            args=(self,),
            daemon=True)
        self._update_thread.start()

        # Recover unfinished callbacks from DB
        if not recover_db:
            return

        # Load unfinished callbacks from DB
        with self._db_lock:
            with make_session_scope(self._db_session) as session:
                pending = session.query(Callback).filter(
                    Callback.acknowledged == False,
                    Callback.retries > 0).all()

        # Add unfinished to retry queue.
        pending = sorted(pending, key=lambda c: c.last_retry)
        with self._lock:
            for cback in pending:
                record = CallbackRecord(cback.id, cback.retries, cback.last_retry)
                self._callbacks[record.id] = record
                self._retry_q.append(record.id)

    def _get_session(self):
        return self._db_session()

    @staticmethod
    def _send_thread_func(job, sent_q):
        """Function used by ThreadPool to send callbacks, one sent
        it places its id on sent_q"""
        callback_id, json, url = job

        try:
            requests.post(url, json=json, timeout=CALLBACK_REQUEST_TIMEOUT)
        except requests.RequestException:
            pass
        except Exception:
            pass

        sent_q.put(callback_id)

    def ack_callback(self, callback_id):
        """Mark callback as acknolewdged, return False if it didn't exist
        True otherwise"""

        # The callback is removed from the callback dictionary to
        # signify it was acknowledged
        with self._lock:
            callback = self._callbacks.pop(callback_id, None)

            # Check there was a callback with the given id
            if callback is None:
                return False

        with self._db_lock:
            with make_session_scope(self._db_session) as session:
                session.query(Callback).filter_by(id=callback_id)\
                        .update({'acknowledged': True})

        return True

    def new_callback(self, callback):
        """Add new callback to queue"""
        callback = Callback.from_callback_data(callback, retries=self.retries+1)

        with self._db_lock:
            with make_session_scope(self._db_session) as session:
                session.add(callback)

        with self._lock:
            record = CallbackRecord(callback.id,
                                    callback.retries,
                                    callback.last_retry)
            self._callbacks[callback.id] = record
            # Set callback as next for delivery
            self._retry_q.appendleft(callback.id)

    def close(self, timeout=None):
        """Close all allocated resources"""
        self._thread_pool.close()
        self._close_flag.set() # To notify update thread
        self._update_thread.join(timeout)
        self._db_session.close()

    def _next_sent(self):
        """Deque an return first callback record ready for delivery or None"""
        retry_limit = datetime.utcnow()-timedelta(seconds=self.retry_period)
        with self._lock:
            callback_id = self._retry_q[0]

            # Check if callback was acknowledged
            callback_record = self._callbacks.get(callback_id, None)
            if callback_record is None:
                return None

            # Check head of the callback is ready to be sent
            if callback_record.last_retry > retry_limit:
                return None

            callback_record = self._retry_q.popleft()

        return callback_record

    def _send_ready(self):
        """Enqueue ready to send callbacks into thread_pool job queue"""

        # Send callbacks ready for a retry
        while len(self._retry_q):

            callback_id = self._next_sent()
            if not callback_id:
                break

            # Construct callback request json
            with self._db_lock:
                with make_session_scope(self._db_session) as session:
                    callback = session.query(Callback).get(callback_id)
                    json = callback.to_request()
                    url = callback.subscription.callback_url

            # Add to thread pool job queue
            try:
                job = (callback_id, json, url)
                self._thread_pool.add_job(job, block=False)
            except queue.Full:
                with self._lock:
                    # If the queue if full wait until next update
                    self._retry_q.appendleft(callback_id)
                    break

    def _process_sent(self):
        """Process callbacks marked as sent by the thread_pool"""
        # Process all callbacks marked as sent by thread_pool
        while True:
            try:
                callback_id = self._sent_q.get(block=True, timeout=1)

                with self._lock:
                    # If callback was acknowledged while being sent discard it
                    # and keep looping
                    record = self._callbacks.get(callback_id, None)
                    if not record:
                        continue

                    # Update callback and enqueue for a retry if there are any remaining,
                    # otherwise discard it.
                    if record.retries > 0:
                        record = CallbackRecord(
                            callback_id,
                            record.retries-1,
                            datetime.utcnow())
                        self._callbacks[callback_id] = record
                        self._retry_q.append(callback_id)
                    else:
                        del self._callbacks[callback_id]

                # Save all changes to db
                with self._db_lock:
                    with make_session_scope(self._db_session) as session:
                        update_fields = {
                            'retries': record.retries,
                            'last_retry': record.last_retry}
                        session.query(Callback).filter_by(id=record.id)\
                            .update(update_fields)

            except queue.Empty:
                # No callbacks remainig at the queue
                break

    @staticmethod
    def _update_func(callback_manager):
        """Function used by periodic update thread"""
        while True:
            if callback_manager._close_flag.is_set():
                break
            callback_manager._send_ready()
            callback_manager._process_sent()

    def __len__(self):
        return len(self._callbacks)




class CallbackTask(object):

    QUEUE_SIZE = 4000
    
    def __init__(self, config):
        """
        Arguments:
            config: flask app config
        """
        self._input_q = Queue(CallbackTask.QUEUE_SIZE)

        settings = {'DB_URI': config['SQLALCHEMY_DATABASE_URI']}
        settings.update(config['CALLBACK_CONF'])
        
        self._task = Process(target=CallbackTask._task_func, 
                             args=(self._input_q, settings))
        self._task.start()

    @staticmethod
    def _task_func(input_q, settings):
        """
        Argumenst:
            input_q (multiprocessing.Queue): command input ()
            settings (dict):
        """
        logger.debug("Task running")
        
        # We need to create a new DB session for the process, the existing
        # one can only be used by flask main process and its threads
        db_session = configure_db(settings['DB_URI'])

        # CallbackManager handles all the logic
        callback_manager = CallbackManager(
                                db_session=db_session,
                                retries=settings['RETRIES'], 
                                retry_period=settings['RETRY_PERIOD'],
                                nthreads=settings['NTHREADS'])

        # Main dispatch loop
        while True:

            try:
                cmd, data = input_q.get(timeout=1)

                if cmd == NEW_CALLBACK:
                    # data: <commands.CallbackData>
                    data = pickle.loads(data)
                    logger.debug("New Callback (id: {})".format(data.id))
                    callback_manager.new_callback(data)

                elif cmd == ACK_CALLBACK:
                    # data: <commands.CallbackData.id> -> string
                    logger.debug("Ack Callback (id: {})".format(data))
                    callback_manager.ack_callback(data)

                elif cmd == EXIT_TASK:
                    callback_manager.close()
                    break

                else:
                    logger.debug("Unknown command {}".format(cmd))

            except queue.Empty:
                continue

        input_q.close()
        exit(0)

    def new_callback(self, callback_data):
        self._input_q.put((NEW_CALLBACK, pickle.dumps(callback_data)))

    def ack_callback(self, callback_id):
        self._input_q.put((ACK_CALLBACK, callback_id))

    def close(self):
        self._input_q.put((EXIT_TASK, None))
        self._input_q.close()
        self._task.join()

















