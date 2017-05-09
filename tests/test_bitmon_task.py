from datetime import datetime, timedelta
from unittest import TestCase

from bitcallback.commands import CallbackData, SubscriptionData
from bitcallback.models import Callback, Subscription, SubscriptionState

from bitcallback.bitmon_task import SubscriptionManager
from bitcallback.database import make_session_scope

from .database import create_memory_db



class MockTransactionMonitor(object):

    def __init__(self):
        self.monitored = set()
        self.added = []
        self.deleted = []

    def get_confirmed(self):
        return []

    def add_addr(self, addr):
        self.monitored.add(addr)

    def del_addr(self, addr):
        self.monitored.remove(addr)

    def __len__(self):
        return len(self.monitored)

class TestSubscriptionManager(TestCase):
    
    def setUp(self):
        self.db_session = create_memory_db()

        with make_session_scope(self.db_session) as session:
            self.subs1 = Subscription(
                address='n2SjFgAhHAv8PcTuq5x2e9sugcXDpMTzX7',
                callback_url='http://localhost:9779') 
            self.subs2 = Subscription(
                address='n2SjFgAhHAv8PcTuq5x2e9sugcXDpMTzX7',
                callback_url='http://localhost:9779', 
                expiration=datetime.utcnow()-timedelta(days=300)) 
            self.subs3 = Subscription(
                address='n2SjFgAhHAv8PcTuq5x2e9sugcXDpMTzX7',
                callback_url='http://localhost:9779',
                state=SubscriptionState.canceled) 
            self.subs4 = Subscription(
                address='n2SjFgAhHAv8PcTuq5x2e9suffXspmtztt',
                callback_url='http://localhost:9779') 
            session.add(self.subs1)
            session.add(self.subs2)
            session.add(self.subs3)
            session.add(self.subs4)

        # Create equivalent SubscriptionData commands
        self.com1 = self.subs1.to_subscription_data()
        self.com2 = self.subs2.to_subscription_data()
        self.com3 = self.subs3.to_subscription_data()
        self.com4 = self.subs4.to_subscription_data()

    def tearDown(self):
        #self.subscription_manager.close()
        pass

    def test_load_active_subscription(self):
        """Test active Subscriptions are loaded during initialization"""
        
        # Try Database with no subscriptions
        monitor = MockTransactionMonitor()
        subscription_manager = SubscriptionManager(monitor, self.db_session)

        self.assertEqual(len(subscription_manager), 3)
        self.assertEqual(len(monitor), 2)

    def test_expired_are_discarded(self):
        """Test expired subscription are discarded and their state updated in DB"""
        monitor = MockTransactionMonitor()
        subscription_manager = SubscriptionManager(monitor, self.db_session)

        self.assertEqual(len(subscription_manager), 3)
        self.assertEqual(len(monitor), 2)

        # Calling poll_bitcoin should remove expired subscriptions
        subscription_manager.poll_bitcoin()

        with make_session_scope(self.db_session) as session:
            expired_subs = session.query(Subscription).filter_by(
                                    id=self.subs2.id).first()
        
        self.assertEqual(expired_subs.state, SubscriptionState.expired)
        self.assertEqual(len(subscription_manager), 2)
        self.assertEqual(len(monitor), 2)

    def test_cancel_subscription(self):
        """Test subscription cancelation"""
        monitor = MockTransactionMonitor()
        subscription_manager = SubscriptionManager(monitor, self.db_session)

        # Initial subscriptions loaded from DB during initialization
        self.assertEqual(len(subscription_manager), 3)
        self.assertEqual(len(monitor), 2)

        # Cancel
        subscription_manager.cancel_subscription(self.subs1.id)
        self.assertEqual(len(subscription_manager), 2)
        self.assertEqual(len(monitor), 2) # 2 because one address is duplicated

        subscription_manager.cancel_subscription(self.subs2.id)
        self.assertEqual(len(subscription_manager), 1)
        self.assertEqual(len(monitor), 1)

        subscription_manager.cancel_subscription(self.subs4.id)
        self.assertEqual(len(subscription_manager), 0)
        self.assertEqual(len(monitor), 0)

    def test_add_subscription(self):
        """Test monitoring new subscriptions"""
        monitor = MockTransactionMonitor()
        subscription_manager = SubscriptionManager(monitor,
                                            self.db_session, 
                                            db_reload=False)
        
        subscription_manager.add_subscription(self.com1)
        self.assertEqual(len(subscription_manager), 1)
        self.assertEqual(len(monitor), 1)

        subscription_manager.add_subscription(self.com2)
        self.assertEqual(len(subscription_manager), 2)
        self.assertEqual(len(monitor), 1)

        subscription_manager.add_subscription(self.com4)
        self.assertEqual(len(subscription_manager), 3)
        self.assertEqual(len(monitor), 2)

    def test_db_reload_subscriptions(self):
        """Test RELOAD_SUBSCRIPTIONS configuration option"""
        # Nothing loaded with reload_subscriptions disable
        monitor = MockTransactionMonitor()
        subs_manager = SubscriptionManager(monitor, self.db_session, False)
        self.assertEqual(len(subs_manager), 0)
        self.assertEqual(len(monitor), 0)

        # ALL active subscriptions loaded with reload_subscriptions enabled
        monitor = MockTransactionMonitor()
        subs_manager = SubscriptionManager(monitor, self.db_session, True)
        self.assertEqual(len(subs_manager), 3)
        self.assertEqual(len(monitor), 2)


    def test_set_transaction_monitor(self):
        """Test subscriptions are updated when transaction monitor is changed"""
        monitor = MockTransactionMonitor()
        subscription_manager = SubscriptionManager(monitor, self.db_session)
