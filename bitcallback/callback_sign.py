import ecdsa
import hashlib
from datetime import datetime
import base64
import copy


def _serialize(callback):
    serialized = (
            str(callback['id']) +
            str(callback['created']) +
            callback['txid'] +
            callback['addr'] +
            str(callback['amount'])).encode()
    return serialized
 

def sign_callback(skey, callback):
    """Add signature to callback json dict

    Arguments:
        skey (ecdsa.SigningKey): Private signing key
        callback (dict): Dictionary containig callback json
            version(int): protocol version currently 1
            id (str): Transaction identification string
            txid (str): Transaction id as a hexadecimal string
            addr (str): Address Base58 encoding
            timestamp (int): timestamp for the transaction discovery
            amount (int): Amount of the transaction

    Returns:
        Dict: a copy of the callback with added signature field
    """
    signature = skey.sign(_serialize(callback), hashfunc=hashlib.sha256)
    callback['signature'] = base64.urlsafe_b64encode(signature).decode('utf-8')
    return callback


def verify_callback(vkey, callback):
    """Verify callback  json dict signature

    Arguments:
        vkey (ecdsa.Verifying): Public key used for signature verification.
        callback(dict): json dictionary to verify
    """
    serialized = _serialize(callback)
    signature = base64.urlsafe_b64decode(callback['signature'])

    try:
        vkey.verify(signature, serialized, hashfunc=hashlib.sha256)
        return True
    except ecdsa.BadSignatureError:
        return False
