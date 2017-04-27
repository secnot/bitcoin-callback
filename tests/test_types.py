from unittest import TestCase
from bitcallback.types import BitcoinAddress

class TestBitcoinAddress(TestCase):

    def test_valid(self):
        """Test probable valid address are accepted"""
        valid = [
            "mjgZHpD1AzEixLgcnncod5df6CntYK4Jpi",
            "1F1tAaz5x1HUXrCNLbtMDqcw6o5GNn4xqX",
            "n2SjFgAhHAv8PcTuq5x2e9sugcXDpMTzX7",
            "mgdT2rG2nms1yEWP75C1oc65our7jRp4bj",
            "1NqCDioR4G6TeoxcVxx5wpghQ7UmESD4uz",
            "2N66DDrmjDCMM3yMSYtAQyAqRtasSkFhbmX",
            "mogLTTLNLBVvYw3WxbKGnvMJqeGvqPDpbp",
            "16WKTYdxxd2jp9CLFzQu5HJQpDE485rRUc",
            "mpifG3WbdPsVWHWP7JEQzkz2GNhRzhDKjP"]

        for address in valid:
            BitcoinAddress(address)

    def test_invalid(self):
        """Test invalid addresses are rejected"""
        invalid = [
            # Checksum error
            "m1gZHpD1AzEixLgcnncod5df6CntYK4Jpi",
            "121tAaz5x1HUXrCNLbtMDqcw6o5GNn4xqX",
            "n3SjFgAhHAv8PcTuq5x2e9sugcXDpMTzX7",
            "m4dT2rG2nms1yEWP75C1oc65our7jRp4bj",
            "m5ifG3WbdPsVWHWP7JEQzkz2GNhRzhDKjP",

            # Length error (but valid Base58Check)
            "2REFC168wX4h1",
            "AH5FpvXbhaAYyM194A",
            "C6Vix8wPoc7cemv9Nk16Y2J4PiKQXjFHWyESmaVcoBzEAN4B",

            # Version byte Error (valid length and Base58Check)
            "uPRYFUWTGbeTdeJ1DYBECQGKq2dhgqv5MF", # 1
            "UpjEU4HgKsS8jJq4RD7eE9qdxQ1y7Vg1m",  # 2
            "2HVwCges6goBmbb17FskcUhQtxuuTJsLCW", # 3
            "2gqYBnx9osG4b2j68gD56byCXUAr6moG79",  # 4
            "mLfUZJYh4zNwGyWGj9WrVtpbEwUqUrZKeB", #110
            "n9LgXX9GVMJguqnSmzBVU9NAVwzirtA1fv", #112
            "2MYPkFXtBRKmQnpMdoopwiYxTjpP1rdNmEg", #195
            "2NM4xDkUkqghARgdoreVagoW2zptuN3foh1", #197
            ]

        for address in invalid:
            with self.assertRaises(ValueError):
                BitcoinAddress(address)
