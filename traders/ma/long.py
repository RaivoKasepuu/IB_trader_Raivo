from ibapi.contract import *

from traders.ma.trader import Trader


class LongTrader(Trader):
    def __init__(self, contract: Contract, symbol, units):
        super().__init__(contract, symbol, units)