from bitcallback import app, bitmon_q, callback_q
from flask import Response, abort
from flask_restplus import Resource, Api, fields, reqparse, marshal_with, inputs

from copy import copy

from .database import db_session
from .models import Subscription, Callback, SubscriptionState
from .commands import *
from .types import BitcoinAddress, iso8601
from .fields import IsoDateTime
from .common import unique_id
from .marshalling import (pagination_fields, subscription_fields, 
    subscription_list_fields, nested_subscription_fields, callback_fields, 
    callback_list_fields)

    
api =  Api(app)


DEFAULT_PER_PAGE = 10
DEFAULT_PAGE = 1

def lower_bool(x):
    """Convert booleans to lowercase string"""
    return str(x).lower() if isinstance(x, bool) else x

def build_url(base, params):
    """
    Build GET url by adding query string params to the base

    Arguments:
        base (str): base
        params (dict): query paramenters
    """

    query = ""
    first = True
    for param, value in params.items():
        if first:
            query += "?"
            first = False
        else:
            query += "&"
        
        query += "{}={}".format(param, lower_bool(value))

    return base+query


def build_paginated_url(base, params, page=DEFAULT_PAGE, per_page=DEFAULT_PER_PAGE):
    """Shorcut for build_url with pagination"""
    q = copy(params)
    q['page'] = page
    q['per_page'] = per_page
    return build_url(base, q)



# TODO: Create fake callback
#
#
@app.route('/test_callback')
def test_callback():
    s = Subscription.create(
            address = 'n4r9Ko71tH6t75iM4RuBwXKRn77vNiFBrb',
            callback_url='http://localhost:8080')
  
    db_session.commit()
  
    # Send new callback command to task
    command_data = CallbackData(
            unique_id(), 
            SubscriptionData(s.id, s.address, s.callback_url, s.expiration),
            "Transaction number",
            12)

    print(command_data)
    import pickle
    callback_q.put((NEW_CALLBACK, pickle.dumps(command_data)))

    return 'Created new callback {}'.format(command_data.id)


#TODO: Create fake subscription
@app.route('/test_subscription')
def test_subscription():
    s = Subscription(
            address = 'n2SjFgAhHAv8PcTuq5x2e9sugcXDpMTzX7',
            callback_url='http://localhost:8080')
    db_session.add(s)
    db_session.commit()
  
    c = Callback(
        subscription_id = s.id,
        txid ="Transaction number",
        amount = 12)

    db_session.add(c)
    db_session.commit()

    # Send new subscription to bitcoin monitor task
    bitmon_q.put((NEW_SUBSCRIPTION, 
        SubscriptionData(s.id, s.address, s.callback_url, s.expiration)))

    #print(Subscription.query.all())
    return 'Created new subscription! (id:)'.format(s.id)

#TODO: USe models vs parsers......


# PAGINATION
#############

pagination_arguments = reqparse.RequestParser()
pagination_arguments.add_argument(
        'per_page', type=int, required=False,
        choices=list(range(1, 51)), default=10,
        help='Elements per page')
pagination_arguments.add_argument(
        'page', type=int, required=False,
        default=1, help='Page number')



# SUBSCRIPTIONS
################

subscription_ns = api.namespace('subscription', description='Subscription operations')


# Subscription creation json parser POST
subscription_parser = reqparse.RequestParser()

subscription_parser.add_argument(
        'address', dest='address',
        required=True, type=BitcoinAddress,
        help='Bitcoin address')
subscription_parser.add_argument(
        'callback_url', dest='callback_url',
        required=True, type=inputs.url,
        help='Callback post url')
subscription_parser.add_argument(
        'expiration', dest='expiration',
        required=False, type=iso8601, #inputs.datetime_from_iso8601
        help='Expiration date (iso8601 format)')

# Subscription list pagination and query
subscription_query_args = pagination_arguments.copy()
subscription_query_args.add_argument('state',
        required=False, type=SubscriptionState)
subscription_query_args.add_argument('address', dest='address',
        required=False, type=BitcoinAddress)

# Subscription patch parser for subs cancelation
subscription_patch_parser = reqparse.RequestParser()
subscription_patch_parser.add_argument(
        'state', dest='state',
        required=True, type=SubscriptionState,
        choices=(SubscriptionState.canceled,), 
        help='Only accepted state change is to "canceled"')


@subscription_ns.route('')
class SubscriptionList(Resource):

    @marshal_with(subscription_list_fields)
    @api.expect(subscription_query_args, validate=False)
    def get(self):
        """Return subscription list"""
        args = subscription_query_args.parse_args()
        page = args.pop('page')
        per_page = args.pop('per_page')
        query_params = {k: v for k, v in args.items() if v is not None}

        subs = Subscription.query.\
                filter_by(**query_params).\
                order_by(Subscription.id.desc()).\
                paginate(page, per_page)

        # Construct pagination next and previous links
        paging = {"next": None, "prev": None}
        url =  "/subscription"

        if subs.has_prev:
            paging['prev'] = build_paginated_url(url, query_params, page-1, per_page)

        if subs.has_next:
            paging['next'] = build_paginated_url(url, query_params, page+1, per_page)
       
        return {"subscriptions":subs.items, "paging":paging}


    @marshal_with(subscription_fields)
    @api.expect(subscription_parser, validate=True)
    def post(self):
        """Create new subscription"""
        args = subscription_parser.parse_args()
        subs = Subscription.create(**args)

        # Commit subscription before signaling monitor task
        db_session.commit()
        
        # Send new subscription message to bitcoin monitor task
        bitmon_q.put((NEW_SUBSCRIPTION, 
            SubscriptionData(subs.id, subs.address, subs.callback_url, subs.expiration)))
        return  subs

@subscription_ns.route('/<int:id>', endpoint='subscription_detail')
class SubscriptionDetail(Resource):
    @marshal_with(subscription_fields)
    def get(self, id):
        """Get subscription details"""
        return Subscription.get_or_404(id)

    @marshal_with(subscription_fields)
    def patch(self, id):
        """Cancel subscription"""
        subs = Subscription.get_or_404(id)
        args = subscription_patch_parser.parse_args()
        
        if subs.state != SubscriptionState.canceled:
            subs.state = args['state']
            subs.save()
            db_session.commit()

            # Send cancelation message to bitcoin monitor task
            bitmon_q.put((CANCEL_SUBSCRIPTION, subs.id))
        return subs





# CALLBACK
###########

callback_ns = api.namespace('callback', description='Callback operations')

callback_patch_parser = reqparse.RequestParser()
callback_patch_parser.add_argument(
        'acknowledged', dest='acknowledged',
        required=True, choices=(True,), type=inputs.boolean,
        help='Only Acknowledge callback is allowed')

callback_query_args = pagination_arguments.copy()
callback_query_args.add_argument(
        'subscription', dest='subscription_id',
        required=False, type=int)
callback_query_args.add_argument(
        'acknowledged', dest='acknowledged',
        required=False, type=inputs.boolean)


@callback_ns.route('')
class CallbackList(Resource):

    @marshal_with(callback_list_fields)
    @api.expect(callback_query_args, validate=True)
    def get(self):
        args = callback_query_args.parse_args()
        page = args.pop('page')
        per_page = args.pop('per_page')
        query_params = {k: v for k, v in args.items() if v is not None}

        callb = Callback.query.\
                filter_by(**query_params).\
                order_by(Callback.created.desc()).\
                paginate(page, per_page)

        # Construct pagination next and previous links
        paging = {"next": None, "prev": None}
        url =  "/callback"

        if callb.has_prev:
            paging['prev'] = build_paginated_url(url, query_params, page-1, per_page)

        if callb.has_next:
            paging['next'] = build_paginated_url(url, query_params, page+1, per_page)
       
        return {"callbacks":callb.items, "paging":paging}

@callback_ns.route('/<string:id>')
class CallbackDetail(Resource):
    
    @marshal_with(callback_fields)
    def get(self, id):
        """Get callback details"""
        return Callback.get_or_404(id=id)

    @marshal_with(callback_fields)
    def patch(self, id):
        """Only for callback acknowledgment"""
        # TODO: Raise exception if the callback was already acknowledged
        callb = Callback.get_or_404(id)
        args = callback_patch_parser.parse_args()

        # Return error if the callbacks is already acknowledged
        if not callb.acknowledged:
            callb.acknowledged = args['acknowledged']
            callb.save()
            db_session.commit()

            # Send ack message to callback_task 
            callback_q.put((ACK_CALLBACK, callb.id))
        else:
            abort(403, {'message': "Callback was already acknowledged"})

        return callb


@app.errorhandler(404)
def not_found(error):
    return 'Not found', 404
