from sqlalchemy import (Column, Integer, BigInteger, String,
                        Unicode, DateTime, Enum, Boolean, ForeignKey)
from sqlalchemy.orm import relationship

from flask import abort
from flask_restplus import marshal
from datetime import datetime, timedelta
import enum


from bitcallback.sign_callback import sign_callback
from bitcallback.marshalling import callback_fields
from bitcallback.common import unique_id
from bitcallback.database import Base

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

class BaseMixin(object):
    _repr_hide = ['created_at', 'updated_at']

   # @classmethod
   # def query(cls):
   #     return db.session.query(cls)

    @classmethod
    def get(cls, id):
        return cls.query.get(id)

    @classmethod
    def get_by(cls, **kw):
        return cls.query.filter_by(**kw).first()

    @classmethod
    def get_or_404(cls, id):
        rv = cls.get(id)
        if rv is None:
            abort(404)
        return rv

    @classmethod
    def get_or_create(cls, **kw):
        r = cls.get_by(**kw)
        if not r:
            r = cls(**kw)
            Base.session.add(r)

        return r

    @classmethod
    def create(cls, **kw):
        r = cls(**kw)
        Base.session.add(r)
        return r

    def save(self):
        Base.session.add(self)

    def delete(self):
        Base.session.delete(self)

    def __repr__(self):
        attrs = [n for n in self.__table__.c.keys() if n not in self._repr_hide]
        name_val_lst = ', '.join("%s=%r" % (n, getattr(self, n)) for n in attrs)
        return "%s(%s)" % (self.__class__.__name__, name_val_lst)

    def filter_string(self):
        return self.__str__()


class Subscription(Base, BaseMixin):
    # TODO: THIS MODEL IS INMUTABLE and once it's created the client
    # can only change state to canceled
    __tablename__ = 'subscriptions'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Monitored bitcoin address
    address = Column(String(40))

    # Url where the callbacks are sent
    callback_url = Column(Unicode(1024), default='')

    # Date of creation
    created = Column(DateTime,
                     default=lambda: datetime.utcnow().replace(microsecond=0))

    # Date this subscription is terminated
    expiration = Column(DateTime,
            default=lambda: (datetime.utcnow()-timedelta(days=30)).replace(microsecond=0))

    #
    state = Column(Enum(SubscriptionState),
                   default=SubscriptionState.active)

    #
    callbacks = relationship('Callback', backref='subscription', lazy='joined')



class Callback(Base, BaseMixin):
    """Callback is the record for transaction notifications"""
    __tablename__ = 'callbacks'

    id = Column(String(32), primary_key=True, default=unique_id)

    subscription_id = Column(Integer, ForeignKey('subscriptions.id'))

    # Bitcoin transaction hash/id and addrs for this callback
    txid = Column(String(64))
    amount = Column(BigInteger, default=0)

    # Creation and last sent times
    created = Column(DateTime, default=datetime.utcnow)
    last_retry = Column(DateTime,
                        default=lambda: datetime.utcnow()-timedelta(minutes=10))

    # Remaining retries (decremented each time it's sent)
    retries = Column(Integer, default=3)

    # Callback was acknowledged
    acknowledged = Column(Boolean, default=False)

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

