from unittest import TestCase
from queue import Queue
from datetime import datetime
from bitcallback.callback_task import CallbackManager
from bitcallback.commands import CallbackData, SubscriptionData

import threading
import datetime
import time
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base 
from sqlalchemy.pool import QueuePool, NullPool, StaticPool
from bitcallback.models import Callback, Subscription

from http.server import BaseHTTPRequestHandler, HTTPServer




def create_memory_db():
    """Configure temp memory database for testing"""
    engine = create_engine('sqlite:///:memory:',
        connect_args={'check_same_thread':False},
        poolclass=StaticPool) 
    # See for explanation on engine options:
    # http://www.sameratiani.com/2013/09/17/flask-unittests-with-in-memory-sqlite.html
    # http://sqlite.org/inmemorydb.html
   
    db_session = scoped_session(sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine))
 
    # Create model tables
    Callback.metadata.create_all(engine)
    Subscription.metadata.create_all(engine)
    return db_session




class TestCallbackRequests(TestCase):
    """Test CallbackManager actuallly send callbacks with a fake server"""

    @staticmethod
    def http_server(request_queue):
        
        class TestHttpRequestHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.data_string = self.rfile.read(int(self.headers['Content-Length']))
                request_queue.put(json.loads(self.data_string.decode()))
                self.send_response(200, '3434')

        server_address = ('127.0.0.1', 9779)
        httpd = HTTPServer(server_address, TestHttpRequestHandler)
        
        # Listen to a single request, use server_forever and shutdown 
        # for more than one
        httpd.handle_request()
        httpd.server_close()

    def setUp(self):
        # Initialized in memory test db
        self.db_session = create_memory_db()
 
        # Subscription where all test callbacks will oritinate
        self.subscription = Subscription(
            address='n2SjFgAhHAv8PcTuq5x2e9sugcXDpMTzX7',
            callback_url='http://localhost:9779') 
        session = self.db_session()
        session.add(self.subscription)
        session.commit()
        session.close()

        self.subscription_data = SubscriptionData(
            id=self.subscription.id,
            address=self.subscription.address,
            expiration=self.subscription.expiration,
            callback_url=self.subscription.callback_url)

        # Queue to store callback requests received by http_server thread
        self.requests = Queue()
        
        # Launch listen server
        self.http_server = threading.Thread(
                target=TestCallbackRequests.http_server, 
                args=(self.requests,), daemon=True)

        self.http_server.start()
        time.sleep(0.1)

        # Launch server
        self.callback_manager = CallbackManager(
            self.db_session, 'a valid ec signing key', 
            retries=3, nthreads=5, retry_period=30)

    def tearDown(self):
        self.callback_manager.close()

    def test_send_callback(self):
        """Check callback is actually used"""
        callback_data = CallbackData(
            id='ewb7RZJISGWjGEe-outhEFNB4ZYsLki9',
            subscription=self.subscription_data,
            txid='9e830d2f858a9382f5a6d8ec224f0ba4d93752a417063c3af612725112741ba8',
            amount=44)

        self.callback_manager.new_callback(callback_data)
        time.sleep(0.2)
        
        # Compare request received by fake server
        request = self.requests.get()
        fields = ['id', 'txid', 'acknowledged', 'subscription', 
                'last_retry', 'created', 'amount', 'retries']
        self.assertEqual(len(request), len(fields))
        for f in fields:
            self.assertTrue(f in request)

        self.assertEqual(request['txid'], callback_data.txid)
        self.assertEqual(request['id'], callback_data.id)
        self.assertEqual(request['amount'], callback_data.amount)



class TestCallbackDB(TestCase):


    def setUp(self):
        self.db_session = create_memory_db()

        # Create subscription that will be used during tests
        self.subscription = Subscription(
            address='n2SjFgAhHAv8PcTuq5x2e9sugcXDpMTzX7',
            callback_url='http://localhost:8080') 
        session = self.db_session()
        session.add(self.subscription)
        session.commit()
        session.close()

        # Subscription as a command data
        self.subscription_data = SubscriptionData(
            id=self.subscription.id,
            address=self.subscription.address,
            expiration=self.subscription.expiration,
            callback_url=self.subscription.callback_url)

        self.callback_manager = CallbackManager(
            self.db_session, 'a valid ec signing key', 
            retries=3, nthreads=5, retry_period=30)
        
    def tearDown(self):
        self.callback_manager.close()

    def test_new_callback(self):
        """Test calling new_callback creates a new DB record"""
        callback_data = CallbackData(
            id='ewb7RZJISGWjGEe-outhEFNB4ZYsLki9',
            subscription=self.subscription,
            txid='9e830d2f858a9382f5a6d8ec224f0ba4d93752a417063c3af612725112741ba8',
            amount=44)

        self.callback_manager.new_callback(callback_data)
        time.sleep(0.1)

        # Check callback was saved to DB
        session = self.db_session()
        cb = session.query(Callback).get(callback_data.id)
       
        # Test callback refers correct subscription
        self.assertEqual(cb.subscription.id, self.subscription.id)

        # Check creation datetime roughly ok
        time_since_creation = datetime.datetime.utcnow()-cb.created
        self.assertTrue(time_since_creation<datetime.timedelta(seconds=1))

        # Check retries
        self.assertEqual(cb.retries, 4) # 1+3 original send + retries 
        self.assertEqual(cb.txid, callback_data.txid)
        self.assertEqual(cb.amount, callback_data.amount)
        self.assertEqual(cb.acknowledged, False)
        time.sleep(2)

    def test_ack_callback(self):
        """Test ack_callback mark db record as acknowledged"""
        callback_data = CallbackData(
            id='ewb7RZJISGWjGEe-outhEFNB4ZYsLki9',
            subscription=self.subscription,
            txid='9e830d2f858a9382f5a6d8ec224f0ba4d93752a417063c3af612725112741ba8',
            amount=44)

        self.callback_manager.new_callback(callback_data)
        time.sleep(0.1)
        cb = self.db_session.query(Callback).get(callback_data.id)
        self.assertEqual(cb.acknowledged, False)

        # Try to acknowledge
        self.callback_manager.ack_callback(callback_data.id)
        time.sleep(0.1)
       
        # Check status has changed
        cb = self.db_session.query(Callback).get(callback_data.id)
        self.assertEqual(cb.acknowledged, True)
    
    def test_recover_db(self):
        """Check unfinished callbacks are reloaded from db after a restart"""
        callback_data = CallbackData(
            id='ewb7RZJISGWjGEe-outhEFNB4ZYsLki9',
            subscription=self.subscription,
            txid='9e830d2f858a9382f5a6d8ec224f0ba4d93752a417063c3af612725112741ba8',
            amount=44)

        self.assertEqual(len(self.callback_manager), 0)
        self.callback_manager.new_callback(callback_data)
        self.assertEqual(len(self.callback_manager), 1)

        # Restart
        self.callback_manager.close()
        new_manager = CallbackManager(
            self.db_session, 'a valid ec signing key', 
            retries=30, nthreads=5, retry_period=30,
            recover_db=True)
        self.assertEqual(len(new_manager), 1)
        new_manager.close()

        # Try once again with recovery disabled
        another_manager = CallbackManager(
            self.db_session, 'a valid ec signing key', 
            retries=30, nthreads=5, retry_period=30,
            recover_db=False)
        self.assertEqual(len(another_manager), 0)
        another_manager.close()















