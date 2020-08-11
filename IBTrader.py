# Below are the global variables

from threading import Thread

from ibapi.client import *
from ibapi.wrapper import *

from traders.ma.trader import Trader


class TestWrapper(EWrapper):

    def __init__(self, traders, secondaryTrader=None):
        super().__init__()
        self.traders = traders
        for trader in traders:
            if secondaryTrader is None:
                trader.traderApp = self
            else:
                trader.traderApp = secondaryTrader

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


class TestClient(EClient):

    def __init__(self, wrapper):
        EClient.__init__(self, wrapper)


class TestApp(TestWrapper, TestClient):
    def __init__(self, ipaddress, portid, traders):
        TestWrapper.__init__(self, traders)
        TestClient.__init__(self, wrapper=self)

        self.connect(ipaddress, portid, 12)

        thread = Thread(target=self.run)
        thread.start()
        setattr(self, "_thread", thread)


if __name__ == '__main__':

    traderDictList = [
        {"reqId": 1, "trader": Trader('SOXL', units=400)},
        {"reqId": 2, "trader": Trader('TECL', units=400)},
        {"reqId": 3, "trader": Trader('AAPL', units=400)}
    ]

    app = TestApp("127.0.0.1", 7496, traderDictList)
    time.sleep(5)

    for traderDict in traderDictList:
        reqId = traderDict['reqId']
        trader = traderDict['trader']
        app.reqRealTimeBars(reqId, trader.contract, 30, "TRADES", False, [])
