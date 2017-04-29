"""
commands.py

Common constants and classes used for threads/processes messaging
"""
from collections import namedtuple

# Start/Stop task
EXIT_TASK = "exit"   # Save current status and exit
PAUSE_TASK = "pause"  # Pause task execution
START_TASK = "start"  # Restart paused task

# Bitcoin monitoring task
NEW_SUBSCRIPTION = "new_subscription"    # Start monitoring bitcoin address
CANCEL_SUBSCRIPTION = "cancel_subscription"    # Stop monitoring bitcoin address

# Callback task
NEW_CALLBACK = "new_callback"  # New callback ready to send
ACK_CALLBACK = "ack_callback"  # A callback was ackd by the client

# Inmutable command data
SubscriptionData = namedtuple('SubscriptionData', ['id', 'address', 'callback_url', 'expiration'])
CallbackData = namedtuple('CallbackData', ['id', 'subscription', 'txid', 'amount'])

