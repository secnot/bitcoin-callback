from multiprocessing import Process, Queue
from collections import defaultdict
import datetime
import time
import logging
import heapq
import pickle
from .bitmon import TransactionMonitor
import bitcoin
import queue
import json
import sqlalchemy


from bitcallback.common import unique_id
from bitcallback.models import Block, Callback, Subscription, SubscriptionState
from bitcallback.commands import (EXIT_TASK, NEW_SUBSCRIPTION, CANCEL_SUBSCRIPTION,
                                  NEW_CALLBACK, SubscriptionData, CallbackData)
from bitcallback.database import make_session_scope, configure_db

#
BITCOIN_UPDATE_PERIOD = 5 # second between updates



logger = logging.getLogger("Bitcoin")


class SubscriptionManager(object):
    """
    Poll bitcoind rpc and send notification when there is a transaction from
    or to a subscribed address
    """

    def __init__(self, monitor, db_session, db_reload=True):
        """
        Arguments:
            monitor (bitmon.TransactionMonitor): Initialized monitor.
            db_session (scoped_session):
            db_reload (bool): Reload subscriptions from database
        """

        # Subscriptions by address
        self._subs_by_addr = defaultdict(set)

        #
        self._subs_by_id = dict()

        #
        self.set_transaction_monitor(monitor)

        self._db_session = db_session

        # Subscription list sorted by expiration date
        self._expiration_table = []
        heapq.heapify(self._expiration_table)

        # Load stil active subscriptions from db
        if not db_reload:
            return

        with make_session_scope(self._db_session) as session:
            active_subs = session.query(Subscription).filter_by(
                    state=SubscriptionState.active).all()
        
        for sub in active_subs:
            # Expired subscriptions will be discarded the first time poll_bitcoin
            # is called
            logger.debug("Loaded Subscription: {}".format(sub))
            sub_data = SubscriptionData(sub.id, sub.address, 
                                        sub.callback_url, sub.expiration)
            self.add_subscription(sub_data)   

    @property
    def current_block(self):
        return self._monitor.current_block

    def set_transaction_monitor(self, monitor):
        """Set new transaction monitor, and configure it to monitor all
        currently subscribed addresses.

        Arguments:
            monitor (bitmon.TransactionMonitor|None):
        """
        self._monitor = monitor
        
        # When connection is lost it can be None until a reconnect
        if monitor is not None:
            for addr in self._subs_by_addr.keys():
                monitor.add_addr(addr)

    def add_subscription(self, subscription=SubscriptionData):
        """
        Arguments:
            subscription (SubscriptionData):
        """
        assert isinstance(subscription, SubscriptionData)

        if self._monitor is not None and subscription.address not in self._subs_by_addr:
            self._monitor.add_addr(subscription.address)

        self._subs_by_addr[subscription.address].add(subscription)
        self._subs_by_id[subscription.id] = subscription
        
        # Add subscription to expiration table sorted by expiration datetime
        heapq.heappush(self._expiration_table,
                       (subscription.expiration, subscription.id))

    def cancel_subscription(self, subscription_id):
        """
        Arguments:
            subscription_id (int):
        """
        try:
            subscription = self._subs_by_id.pop(subscription_id)
            self._subs_by_addr[subscription.address].remove(subscription)
           
            # if it's the only remainig subscription for the address
            # stop monitoring
            if not len(self._subs_by_addr[subscription.address]):
                if self._monitor is not None:
                    self._monitor.del_addr(subscription.address)
                del self._subs_by_addr[subscription.address]

        except KeyError:
            logger.debug("Unable to cancel unknown subscription {}".format(subscription_id))

    def _remove_expired_subscriptions(self):
        """
        """
        expired = []

        now = datetime.datetime.utcnow()

        # Remove expired subscriptions
        while self._expiration_table and self._expiration_table[0][0]<now:
            expiration, sub_id = heapq.heappop(self._expiration_table)

            # If the subscription isn't canceled store id
            if sub_id in self._subs_by_id:
                expired.append(sub_id)
            
            self.cancel_subscription(sub_id)

        if not expired:
            return 

        # Change status to expired for all expired and still active subscriptions
        with make_session_scope(self._db_session) as session:
            session.query(Subscription).filter(Subscription.id.in_(expired)).\
                    update({'state':SubscriptionState.expired}, synchronize_session=False)
        
        # Stop monitoring for all the subscription
        for sub_id in expired:
            self.cancel_subscription(sub_id)

    def _transaction_to_callbacks(self, transaction):
        """Split transaction into as many callbacks as needed to
        notify all the subscriptions

        Arguments:
            transaction (bitmon.Transaction)
        """
        thash = transaction.hash
        subscriptions = self._subs_by_addr
        callbacks = []

        # Generate callbacks required for each transaction. 
        for addr, amount in transaction.tout.items():
            # Have to check because it's a defaultdict and will populate
            # with empty sets otherwise
            if addr not in subscriptions:
                continue

            for subs in subscriptions[addr]:
                change = amount - transaction.tin.get(addr, 0)
                if change:
                    callback = CallbackData(unique_id(), subs, thash, amount)
                    callbacks.append(callback)

        for addr, amount in transaction.tin.items():
            if addr not in subscriptions or addr in transaction.tout:
                continue

            for subs in subscriptions[addr]:
                callback = CallbackData(unique_id(), subs, thash, -amount)
                callbacks.append(callback)

        return callbacks

    def poll_bitcoin(self):
        """Poll bitcoin blockchain for transactions to or from one of
        the monitored addresses"""
        # Removed expired subscriptions before generating callbacks
        self._remove_expired_subscriptions()

        logger.debug("BLOCK: {}".format(self._monitor.current_block))
        #
        transactions = self._monitor.get_confirmed()

        callbacks = []
        for tran in transactions:
            callbacks.extend(self._transaction_to_callbacks(tran))
        return callbacks

    def close(self):
        return 

    def __contains__(self, key):
        """Return True if the id or address is being monitored"""
        if isinstance(key, int):
            return key in self._subs_by_id
        else:
            return key in self._subs_by_addr

    def __len__(self):
        """Return number of active subscriptions"""
        return len(self._subs_by_id)





class BitmonTask(object):

    QUEUE_SIZE = 4000
    
    def __init__(self, callback_task, config):
        self._input_q = Queue(BitmonTask.QUEUE_SIZE)
        
        settings = {'DB_URI': config['SQLALCHEMY_DATABASE_URI']}
        settings.update(config['BITCOIN_CONF'])
        self._settings = settings
        self._callback_task = callback_task
        self._task = Process(target=self.bitcoin_task,
                             args=(self._input_q, callback_task, settings))
        self._task.start()

    def _init_task(self, settings):
        """Initialize task after process is forked"""
        # Last time bitcoind was polled or reconnect tried
        self._last_update = time.perf_counter()
 
        # We need to create a new DB session for the process, because the
        # one used by flask can be only be share between threads.
        self._db_session = configure_db(self._settings['DB_URI'])

        # Find block number where monitoring stoped last time
        self._current_block = -1 # Start by newest block

        if self._settings['START_BLOCK'] == 'last':
            with make_session_scope(self._db_session) as session:
                try:
                    block = session.query(Block).one()
                    self._current_block = block.block_number
                except sqlalchemy.orm.exc.NoResultFound:
                    # Not found, it can happen the first time the app is executed
                    # so there is no need to log the exception
                    pass
        
        # bitcoin lib chain selection
        bitcoin.SelectParams(self._settings['CHAIN'])
    
        # It will be initialized later by reconnect code
        self._monitor = None
 
        # Transaction monitor is not provided so it is not initialized here
        # so it's treated later as if the connection was lost.
        self._subscription_manager = SubscriptionManager(
                                        self._monitor, # Init later
                                        self._db_session,
                                        settings['RELOAD_SUBSCRIPTIONS'])

    def _save_block_number(self, block_number):
        """Save block number into db, create row if it doesn't exist, update
        if it does.
        
        Arguments:
            block_number (int): positive integer
        """
        assert isinstance(block_number, int) and block_number>=0

        with make_session_scope(self._db_session) as session:
            try:
                block = session.query(Block).one()
                block.block_number = block_number
                session.add(block)
            except sqlalchemy.orm.exc.NoResultFound:
                block = Block(block_number=block_number)
                session.add(block)

    def _connect_bitcoind(self):
        """
        Try to reconnect to bitcoind server

        Returns:
            (bool): True if was reconnected false otherwise
        """
        try:
            proxy = bitcoin.rpc.Proxy(service_url=self._settings['BITCOIND_URL'])
            monitor = TransactionMonitor(proxy, self._settings['CONFIRMATIONS'], 
                                         self._current_block)
            self._subscription_manager.set_transaction_monitor(monitor)
            self._monitor = monitor
            logger.info("Bitcoind connected")
            return True
        except (ConnectionError, bitcoin.rpc.InWarmupError) as err:
            logger.debug("Bitcoind reconnect error: {}".format(err.__class__.__name__))
        except Exception as err:
            logger.error(err, exc_info=True)
        
        return False

    def _send_confirmed(self):
        """Look for new confirmed transactions, and send corresponding callbacks
        to callback task
        """
        try:
            callbacks = self._subscription_manager.poll_bitcoin()

        except (json.JSONDecodeError, ConnectionError) as err:
            # This error is raised when connection to bitcoind is lost.
            subscription_manager.set_transaction_monitor(None)
            monitor_connected = False
            logger.info("Bitcoind connection lost")
        except Exception as err:
            subscription_manager.set_transaction_monitor(None)
            monitor_connected = False
            logger.error(err, exc_info=True)

        # Send Callbacks to notification task
        for cback in callbacks:
            logger.debug("New callback: {}".format(cback.id))
            self._callback_task.new_callback(cback)

        # If the block number has changed it means that a new block has 
        # been accepted, so we need to save the number to db. It is saved
        # after the callbacks are sent for data consistency.
        new_block = self._subscription_manager.current_block
        if self._current_block != new_block:
            self._save_block_number(new_block)
            self._current_block = new_block

    def bitcoin_task(self, input_q, callback_task, settings):
        """
        Arguments:
            input_q (multiprocessing.Queue): Command input queue
                NEW_SUBSCRIPTION, CANCEL_SUBSCRIPTION, EXIT_TASK
            callback_task (.callback_task.CallbackTask): callback delivery task
            settings(dict): Configurations settings/constants
        """
        self._init_task(self._settings)
        logger.debug("Task running")

        # Main dispatch loop
        while True:

            try:
                cmd, data = input_q.get(block=True, timeout=1)
                if cmd == NEW_SUBSCRIPTION:
                    logger.debug("New Subscription (id: {})".format(data.id))
                    self._subscription_manager.add_subscription(data)

                elif cmd == CANCEL_SUBSCRIPTION:
                    logger.debug("Cancel Subscription (id: {})".format(data.id))
                    self._subscription_manager.cancel_subscription(data)

                elif cmd == EXIT_TASK:
                    break

                else:
                    logger.debug("Unknown command {}".format(cmd))

            except queue.Empty:
                pass

            # Only periodical bitcoin updates and reconnect attempts
            if time.perf_counter()-self._last_update < BITCOIN_UPDATE_PERIOD:
                continue
            else:
                self._last_update = time.perf_counter()

            # If connection was lost or not initialized try to reconnect
            if self._monitor is None:
                if not self._connect_bitcoind():
                    continue
       
            # Send confirmed callbacks if any
            self._send_confirmed()

        # Close resource before exiting
        input_q.close()
        exit(0)
    
    # USED BY FLASK MAIN PROCESS
    ############################

    def new_subscription(self, subscription_data):
        self._input_q.put((NEW_SUBSCRIPTION, subscription_data))

    def cancel_subscription(self, subscription_id):
        self._input_q.put((CANCEL_SUBSCRIPTION, subscription_id))

    def close(self):
        self._input_q.put((EXIT_TASK, None))
        self._input_q.close()
        self._task.join()
