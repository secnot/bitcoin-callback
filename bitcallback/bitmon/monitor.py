import bitcoin
import bitcoin.rpc as rpc
from bitcoin.core import str_money_value, b2lx, b2x, x
from bitcoin.wallet import CBitcoinAddress, CBitcoinAddressError, P2SHBitcoinAddress, P2PKHBitcoinAddress
from .transaction import Transaction
from .cache import TxOutCache



class TransactionMonitor(object):
    """Monitor blockchains for confirmed transactions where at least
    one of the outputs is for one of the monitored addresses"""

    def __init__(self, proxy, confirmations=1, start_block=-1):
        """
        Arguments:
            proxy: bitcoin.rpc proxy object
            confirmations(int): Number of confirmations required before
            cache_size: Number of blocks being monitored, it has to
                be larger than the max number of confirmations.
            start_block (int): Number of the block where monitoring
                starts, -1 for last
        """
        assert confirmations > 0

        self._confirmations = confirmations

        # Address being monitored
        self._monitored = set()

        # Bitcoinlib rpc proxy
        self._proxy = proxy
        
        # Transaction output cache
        self._cache = TxOutCache(self._proxy, max_size=20000)

        #
        if start_block < 0:
            start_block = proxy.getblockcount()+start_block+1

        self._current_block = start_block

    def _load_block(self, blocknum):
        blockhash = self._proxy.getblockhash(blocknum)
        return self._proxy.getblock(blockhash)

    def _is_monitored_addr(self, addr):
        return addr in self._monitored

    def _is_monitored_transaction(self, tran):
        """Check if transaction has at least one output for a monitored address
       
        Arguments:
            tran (Transaction): Transaction object

        Returns:
            bool: True if any of the transaction inputs or outputs are monitored
                False otherwise
        """
        for addr in tran.tout.keys():
            if self._is_monitored_addr(addr):
                return True

        for addr in tran.tin.keys():
            if self._is_monitored_addr(addr):
                return True

        return False

    def _process_block_transactions(self, block):
        """Get block Transactions
        
        Arguments:
            block (bitcoin.CBlock)

        Returns:
            list: [Transaction, Transaction, ....]
        """
        cache = self._get_cache()
        return [Transaction(tx, cache) for tx in block.vtx]

    def _get_cache(self):
        return self._cache

    def get_confirmed(self):
        """
        Get confirmed transactions involving any of the monitored addresses

        Returns:
            list: [Transaction, Transaction, ...]
        """ 
        transactions = []
        
        lastblock = self._proxy.getblockcount()
        if lastblock == self._current_block:
            return []

        if self._current_block < lastblock:
            monitored_block = self._current_block-self._confirmations+1
            block = self._load_block(monitored_block)
            trans = self._process_block_transactions(block)
            transactions.extend(trans)
     
            self._current_block += 1
 
        return [t for t in transactions if self._is_monitored_transaction(t)]

    # ADD/DEL Address, text existence
    def add_addr(self, addr):
        assert isinstance(addr, str)
        self._monitored.add(addr)

    def del_addr(self, addr):
        self._monitored.remove(addr)

    def __contains__(self, addr):
        return addr in self._monitored


