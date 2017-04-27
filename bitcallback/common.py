import base64
import uuid

def unique_id():
    """Return a 32 chareacter long random string"""
    uid = uuid.uuid4().bytes+uuid.uuid4().bytes
    return base64.urlsafe_b64encode(uid).decode('utf-8')[0:32]
