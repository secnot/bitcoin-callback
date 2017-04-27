from flask_restplus import fields

class IsoDateTime(fields.Raw):
    def format(self, value):
        """Discard microseconds"""
        return value.replace(microsecond=0).isoformat()


