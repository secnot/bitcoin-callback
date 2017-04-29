"""
marshalling

REST api response marshalling fields
"""

from flask_restplus import fields
from .fields import IsoDateTime


pagination_fields = {
    'next': fields.String,
    'prev': fields.String
}

subscription_fields = {
    'id': fields.Integer,
    'address': fields.String,
    'callback_url': fields.String,
    'created': IsoDateTime,
    'expiration': IsoDateTime,
    'state': fields.String,
}

subscription_list_fields = {
    'subscriptions': fields.List(fields.Nested(subscription_fields)),
    'paging': fields.Nested(pagination_fields)
}

nested_subscription_fields = {
    'id': fields.Integer,
    'address': fields.String,
}

callback_fields = {
    'id': fields.String,
    'subscription': fields.Nested(nested_subscription_fields),
    'txid': fields.String,
    'amount': fields.Integer,
    'created': IsoDateTime,
    'last_retry': IsoDateTime,
    'retries': fields.Integer,
    'acknowledged': fields.Boolean
}


callback_list_fields = {
    'callbacks': fields.List(fields.Nested(callback_fields)),
    'paging': fields.Nested(pagination_fields)
}


