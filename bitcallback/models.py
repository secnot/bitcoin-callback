from flask_sqlalchemy import SQLAlchemy

from flask import abort
from flask_restplus import marshal
from datetime import datetime, timedelta
import enum


from bitcallback.marshalling import callback_fields
from bitcallback.common import unique_id
from bitcallback.commands import SubscriptionData, CallbackData



class SubscriptionState(enum.Enum):
    active = 'active'
    canceled = 'canceled'
    expired = 'expired'
    suspended = 'suspended'

    def __str__(self):
        # Hide class name
        return self.name

class CallbackState(enum.Enum):

    waiting = 1 #
    acknowledged = 2
    expired = 3

    def __str__(self):
        return self.name


db = SQLAlchemy()

class Subscription(db.Model):
    # TODO: THIS MODEL IS INMUTABLE and once it's created the client
    # can only change state to canceled
    __tablename__ = 'subscriptions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Monitored bitcoin address
    address = db.Column(db.String(40))

    # Url where the callbacks are sent
    callback_url = db.Column(db.Unicode(1024), default='')

    # Date of creation
    created = db.Column(db.DateTime,
                     default=lambda: datetime.utcnow().replace(microsecond=0))

    # Date this subscription is terminated
    expiration = db.Column(db.DateTime,
            default=lambda: (datetime.utcnow()+timedelta(days=30)).replace(microsecond=0))

    #
    state = db.Column(db.Enum(SubscriptionState),
                   default=SubscriptionState.active)

    #
    callbacks = db.relationship('Callback', backref='subscription', lazy='joined')

    def to_subscription_data(self):
        """Equivalent SubscriptionData to the model"""
        return SubscriptionData(id = self.id,
                                address = self.address,
                                callback_url = self.callback_url,
                                expiration = self.expiration)

    def __str__(self):
        return "Subscription {} for {} (exp {})".format(self.id, self.address, self.expiration)



class Callback(db.Model):
    """Callback is the record for transaction notifications"""
    __tablename__ = 'callbacks'

    id = db.Column(db.String(32), primary_key=True, default=unique_id)

    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'))

    # Bitcoin transaction hash/id and addrs for this callback
    txid = db.Column(db.String(64))
    amount = db.Column(db.BigInteger, default=0)

    # Creation and last sent times
    created = db.Column(db.DateTime, default=datetime.utcnow)
    last_retry = db.Column(db.DateTime,
                        default=lambda: datetime.utcnow()-timedelta(minutes=10))

    # Remaining retries (decremented each time it's sent)
    retries = db.Column(db.Integer, default=3)

    # Callback was acknowledged
    acknowledged = db.Column(db.Boolean, default=False)

    def to_request(self, sign_key=None):
        """Generate json callback request

        Arguments:
            sign_key (ecdsa.SigningKey): Private signing key
        """
        json = marshal(self, callback_fields)

        if sign_key:
            return sign_callback(sign_key, self)
        else:
            return json


    @classmethod
    def from_callback_data(cls, callback_data, **kwargs):
        """Create callback record from CallbackData object..

        Arguments:
            callback_data (CallbackData): Command data
            kwargs (dict):
        """
        cb_kwargs = {
            'id': callback_data.id,
            'subscription_id': callback_data.subscription.id,
            'txid': callback_data.txid,
            'amount': callback_data.amount}

        cb_kwargs.update(kwargs)

        return cls(**cb_kwargs)


class Block(db.Model):
    """Single row table to store the last monitored block number"""
    __tablename__ = 'lastblock'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Height for the last monitored block
    block_number = db.Column(db.Integer) 

    #
