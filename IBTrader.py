# Below are the global variables

from threading import Thread

from ibapi.client import *
from ibapi.wrapper import *

from traders.ma.trader import Trader


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
        print('The next valid order id is: ', self.nextorderId)

    def orderStatus(self, orderId, status, filled, remaining, avgFullPrice, permId, parentId, lastFillPrice, clientId,
                    whyHeld, mktCapPrice):
        print('orderStatus - orderid:', orderId, 'status:', status, 'filled', filled, 'remaining', remaining,
              'lastFillPrice', lastFillPrice)

    def openOrder(self, orderId, contract, order, orderState):
        print('openOrder id:', orderId, contract.symbol, contract.secType, '@', contract.exchange, ':', order.action,
              order.orderType, order.totalQuantity, orderState.status)

    def execDetails(self, reqId, contract, execution):
        print('Order Executed: ', reqId, contract.symbol, contract.secType, contract.currency, execution.execId,
              execution.orderId, execution.shares, execution.lastLiquidity)

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

    traderDictList = [
        {"reqId": 1, "trader": Trader('NVDA', units=45)}
    ]

    paperTrader = IBApp("127.0.0.1", 7400, traderDictList)
    time.sleep(5)

    app = IBApp("127.0.0.1", 7496, traders=traderDictList, secondaryTrader=paperTrader)
    time.sleep(5)

    for traderDict in traderDictList:
        reqId = traderDict['reqId']
        trader = traderDict['trader']
        print("RealTimeBars requested from", trader.contract.symbol)
        app.reqRealTimeBars(reqId, trader.contract, 30, "TRADES", False, [])
