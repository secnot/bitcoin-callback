from collections import defaultdict
import time
import pickle
from .bitmon import TransactionMonitor
import bitcoin
import queue
from .common import unique_id


from .commands import (EXIT_TASK, NEW_SUBSCRIPTION, CANCEL_SUBSCRIPTION, NEW_CALLBACK,
                       SubscriptionData, CallbackData)

#
BITCOIN_UPDATE_PERIOD = 5 # second between updates



class SubscriptionManager(object):
    """
    Poll bitcoind rpc and send notification when there is a transaction from
    or to a subscribed address
    """

    def __init__(self, monitor):
        """
        Arguments:
            monitor (bitmon.TransactionMonitor): Initialized monitor.
        """

        # Subscriptions by address
        self._subs_by_addr = defaultdict(set)

        #
        self._subs_by_id = dict()

        #
        self.set_bitcoin_monitor(monitor)

    def set_bitcoin_monitor(self, monitor):
        """Set new transaction monitor, and configure it to monitor all
        currently subscribed addresses.

        Arguments:
            monitor (bitmon.TransactionMonitor):
        """
        for addr in self._subs_by_addr.keys():
            monitor.add_addr(addr)

        self._monitor = monitor

    def add_subscription(self, subscription=SubscriptionData):
        """
        Arguments:
            subscription (SubscriptionData):
        """
        assert isinstance(subscription, SubscriptionData)

        if subscription.address not in self._subs_by_addr:
            self._monitor.add_addr(subscription.address)

        self._subs_by_addr[subscription.address].add(subscription)
        self._subs_by_id[subscription.id] = subscription

    def cancel_subscription(self, subscription_id):
        """
        Arguments:
            subscription_id (int):
        """
        try:
            subscription = self._subs_by_id.pop(subscription_id)
            self._subs_by_addr[subscription.address].remove(subscription)
            self._monitor.del_addr(subscription.address)
        except KeyError:
            pass

    def _transaction_to_callbacks(self, transaction):
        """Split transaction into as many callbacks as needed to
        notify all the subscriptions

        Arguments:
            transaction (bitmon.Transaction)
        """
        thash = transaction.hash
        subscriptions = self._subs_by_addr
        callbacks = []

        for addr, amount in transaction.tout.items():
            # Have to check because it's a defaultdict and will populate
            # with empty sets otherwise
            if addr not in subscriptions:
                #continue
                pass

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
        transactions = self._monitor.get_confirmed()

        callbacks = []
        for tran in transactions:
            callbacks.extend(self._transaction_to_callbacks(tran))

        return callbacks

    def __contains__(self, key):
        """Return True if the id or address is being monitored"""
        if isinstance(key, int):
            return key in self._subs_by_id
        else:
            return key in self._subs_by_addr


def bitcoin_task(input_q=None, callback_q=None, settings=None):
    """
    Argumenst:
        input_q (multiprocessing.Queue): Queue used to receive command
            NEW_SUBSCRIPTION, CANCEL_SUBSCRIPTION, EXIT_TASK
        output_q (multiprocessing.Queue): Queue used to send discovered
            transactions callbacks.
        settings(dict): Configurations settings/constants
            json_url (str): Address for bitcoind node JSON-RPC service
            confirmations(int): Number of confirmations required before a
                transactions is accepted.
            chain (str): Bitcoin chain selector one of
                ('testnet', 'mainnet', 'regtest')
    """
    if not settings:
        settings = {}

    last_update = time.perf_counter()

    # -1 for last block, -2 for the block before it ... and so on
    # TODO: Should read from db wich was the last block processed and
    # continue from there
    start_block = -2

    #TODO: Catch bitcoind proxy connection errors, and reconnect when needed
    bitcoin.SelectParams(settings['CHAIN'], )
    proxy = bitcoin.rpc.Proxy(service_url=settings['BITCOIND_URL'])
    monitor = TransactionMonitor(proxy, settings['CONFIRMATIONS'], start_block)
    submanager = SubscriptionManager(monitor)

    while True:
        try:
            cmd, data = input_q.get(block=True, timeout=1)
            if cmd == NEW_SUBSCRIPTION:
                submanager.add_subscription(data)

            elif cmd == CANCEL_SUBSCRIPTION:
                submanager.cancel_subscription(data)

            elif cmd == EXIT_TASK:
                input_q.close()
                callback_q.close()
                exit(0)

        except queue.Empty:
            pass

        # Look for new confirmed transactions
        if time.perf_counter()-last_update >= BITCOIN_UPDATE_PERIOD:
            last_update = time.perf_counter()

            # Create callbacks required for each transactions
            callbacks = submanager.poll_bitcoin()

            # Send Callbacks to notification task
            for cback in callbacks:
                callback_q.put((NEW_CALLBACK, pickle.dumps(cback)))
