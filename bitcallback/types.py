import datetime
from dateutil import parser
from bitcoin.base58 import CBase58Data

# Supported address version bytes
BITCOIN_VERSION_BYTES = (
        111, # Testnet pubkey hash
        196, # Testnet script hash
        0,   # MainNet pubkey hash
        5)   # MainNet script hash

def iso8601(time):
    """Iso 8601 string to datetime"""
    try:
        iso = parser.parse(time, ignoretz=True)
        return iso
    except Exception:
        raise ValueError('{} is not a valid ISO 8601 format'.format(time)) 

def BitcoinAddress(address):
    """Bitcoin address validation accepts both testnet and mainnet"""
    try: 
        assert isinstance(address, str)
        assert 25 < len(address) < 36
        addr = CBase58Data(address)
        assert addr.nVersion in BITCOIN_VERSION_BYTES
        return address
    except Exception:
        raise ValueError('{} is not a valid bitcoin address'.format(address))

