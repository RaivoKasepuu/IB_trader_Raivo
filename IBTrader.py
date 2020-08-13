# Below are the global variables

from threading import Thread

from ibapi.client import *
from ibapi.wrapper import *

from traders.ma.trader import Trader
import logging


class IBWrapper(EWrapper):

    def __init__(self, traders, secondaryTrader=None):
        super().__init__()

        self.traders = traders
        self.nextorderId = None

        for trader in traders:
            if secondaryTrader is None:
                trader['trader'].traderApp = self
            else:
                trader['trader'].traderApp = secondaryTrader

    def nextValidId(self, orderId: int):
        super().nextValidId(orderId)
        self.nextorderId = orderId
        logging.info('The next valid order id is: %s', self.nextorderId)

    def orderStatus(self, orderId, status, filled, remaining, avgFullPrice, permId, parentId, lastFillPrice, clientId,
                    whyHeld, mktCapPrice):
        logging.info('Order status: %s. Id: %s. Filled: %s', status, orderId, filled)

    def execDetails(self, reqId, contract, execution):
        logging.info('Order executed: %s', contract.symbol, execution.shares)

    def realtimeBar(self,
                    reqId: TickerId,
                    response_time: int, open_: float, high: float, low: float, close: float,
                    volume: int, wap: float, count: int):
        super().realtimeBar(reqId, response_time, open_, high, low, close, volume, wap, count)
        bar = RealTimeBar(response_time, -1, open_, high, low, close, volume, wap, count)
        for t in self.traders:
            if t['reqId'] is reqId:
                t['trader'].newBar(bar)
                break


class IBClient(EClient):

    def __init__(self, wrapper):
        EClient.__init__(self, wrapper)


class IBApp(IBWrapper, IBClient):
    def __init__(self, ipaddress, portid, traders, secondaryTrader=None):
        IBWrapper.__init__(self, traders, secondaryTrader)
        IBClient.__init__(self, wrapper=self)

        self.connect(ipaddress, portid, 12)

        thread = Thread(target=self.run)
        thread.start()
        setattr(self, "_thread", thread)

        tradingApp = self
        if secondaryTrader is not None:
            tradingApp = secondaryTrader
        while True:
            if isinstance(tradingApp.nextorderId, int):
                print('connected')
                print()
                break
            else:
                print('waiting for connection')
                time.sleep(1)


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s-%(levelname)s:%(message)s')

    traderDictList = [
        {"reqId": 1, "trader": Trader('TSLA', units=12)},
        {"reqId": 2, "trader": Trader('NVDA', units=35)},
        {"reqId": 3, "trader": Trader('AMD', units=195)},
        {"reqId": 4, "trader": Trader('TWLO', units=64)}
    ]

    app = IBApp("127.0.0.1", 7400, traders=traderDictList)
    time.sleep(5)

    for traderDict in traderDictList:
        reqId = traderDict['reqId']
        trader = traderDict['trader']
        print("RealTimeBars requested from", trader.contract.symbol)
        app.reqRealTimeBars(reqId, trader.contract, 30, "TRADES", False, [])
