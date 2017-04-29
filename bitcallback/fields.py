"""
fields:

Custom marshalling fields
"""
from flask_restplus import fields

class IsoDateTime(fields.Raw):
    """Convert datetime to is format discarding microseconds"""

    def format(self, value):
        """Discard microseconds"""
        return value.replace(microsecond=0).isoformat()


