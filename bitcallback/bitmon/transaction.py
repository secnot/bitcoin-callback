from bitcoin.core import str_money_value, b2lx
from bitcoin.wallet import CBitcoinAddress, CBitcoinAddressError
from .cache import TxOutCache



class Transaction(object):

    __slots__ = ('hash', 'tout', 'tin')

    def __init__(self, tx, txout_cache):
        """
        Arguments:
            tran (bitcoin.core.CTransaction): Transaction to construct
            txout_cache (TxOutCache):
        """ 
        # GetTxid instead of GetHash for segwit support (bip-0141)
        self.hash = b2lx(tx.GetTxid())

        self.tout = self._process_outputs(tx)
        self.tin = self._process_inputs(tx, txout_cache)

    def _process_inputs(self, tx, cache):
        inputs = {}
        
        if tx.is_coinbase():
            return inputs
    
        for tin in tx.vin:
            addr, value = cache.txout(tin.prevout.hash, tin.prevout.n)
            if value is not None:
                inputs[addr] = inputs.get(addr, 0)+value

        return inputs

    def _process_outputs(self, tx):
        outputs = {}
        
        for txout in tx.vout:
            try:
                addr = str(CBitcoinAddress.from_scriptPubKey(txout.scriptPubKey))
                outputs[addr] = outputs.get(addr, 0)+txout.nValue
            except CBitcoinAddressError:
                pass

        return outputs

    def __hash__(self):
        return hash(self.hash)

    def __eq__(self, other):
        return self.hash == other.hash

    def __repr__(self):
        return "Transaction({})".format(self.hash)
    
    def __str__(self):
        return repr(self)


