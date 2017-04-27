import bitcoin
from bitcoin.wallet import CBitcoinAddress, CBitcoinAddressError
from bitcoin.core import str_money_value, b2lx, b2x, lx
from collections import OrderedDict




class TxOutCache(object):
    """Bitcon transactions outputs LRU Cache """
    
    def __init__(self, proxy, max_size=10000):
        """
        Arguments:
            proxy (bitcoin.rpc.proxy):
            max_size (int):
        """
        self._cache = OrderedDict()
        self._proxy = proxy
        self._max_size = max_size

    def _proccess_tx(self, tx):
        """
        Arguments:
            tx (bitcoin.core.CTransaction): 

        Returns:
            list: list of valid transactions outputs
            [(addr0, value0), ..., (addrN, valueN)]
        """
        outputs = []
        for txout in tx.vout:
            try:
                addr = str(CBitcoinAddress.from_scriptPubKey(txout.scriptPubKey))
                outputs.append((addr, txout.nValue))
            except CBitcoinAddressError:
                outputs.append(('NO_STANDARD', None))

        return outputs

    def _load(self, txid):
        """Load transaction into cache

        Arguments:
            txid (str): Transaction hash
        """
        if txid in self._cache:
            return
        
        tx = self._proxy.getrawtransaction(txid)
        self._cache[txid] = self._proccess_tx(tx)

        if len(self._cache)>self._max_size:
            self._cache.popitem(last=False)

    def txout(self, txid, n):
        """
        Arguments:
            txid (str): Transactions id
            n (int): output number
        """
        if txid not in self._cache:
            # TODO: Only load into cache transaction with more than
            # one standard output. If they have only one it was 
            # consumed by this request.
            self._load(txid)
        else:
            # Move last accessed to cache top
            self._cache.move_to_end(txid)

        return self._cache[txid][n]

    def purge(self):
        self._cache = OrderedDict()
        
    def __len__(self):
        return len(self._cache)
