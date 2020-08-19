# Below are the global variables

from datetime import datetime
from threading import Thread

from ibapi.client import *
from ibapi.wrapper import *

from message.chatbot import ChatBot
from traders.ma.raivo_trader import RaivoTrader

logging.basicConfig(format='%(asctime)s-%(levelname)s:%(message)s', level="WARN")


class IBWrapper(EWrapper):

    def __init__(self, traders, secondaryTrader=None):
        super().__init__()

        self.traders = traders
        self.nextorderId = None
        tickId = 1
        reqId = 1

        for trader in traders:
            trader.reqId = reqId
            trader.tickDataId = tickId
            reqId += 1
            tickId += 1
            if secondaryTrader is None:
                trader.traderApp = self
            else:
                trader.traderApp = secondaryTrader

    def nextValidId(self, orderId: int):
        super().nextValidId(orderId)
        self.nextorderId = orderId
        logging.info('The next valid order id is: %s', self.nextorderId)

    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, permId, parentId, lastFillPrice, clientId,
                    whyHeld, mktCapPrice):
        super().orderStatus(orderId, status, filled, remaining, avgFillPrice, permId, parentId, lastFillPrice, clientId,
                            whyHeld, mktCapPrice)
        logging.warning('Order status: %s. Id: %s. Filled: %s', status, orderId, filled)

    def execDetails(self, reqId, contract, execution):
        logging.warning('Order executed: %s %s %s', contract.symbol, str(execution.price), str(execution.shares))
        for t in self.traders:
            t.hasOrderUpdate(reqId, execution.price, execution.shares, execution)

    def realtimeBar(self,
                    reqId: TickerId,
                    response_time: int, open_: float, high: float, low: float, close: float,
                    volume: int, wap: float, count: int):
        super().realtimeBar(reqId, response_time, open_, high, low, close, volume, wap, count)
        bar = RealTimeBar(response_time, -1, open_, high, low, close, volume, wap, count)
        for t in self.traders:
            if t.reqId is reqId:
                t.newBar(bar)
                break

    def tickByTickMidPoint(self, reqId: int, time: int, midPoint: float):
        super().tickByTickMidPoint(reqId, time, midPoint)
        for t in self.traders:
            if t.tickDataId is reqId:
                t.newMidpoint(midPoint)
                break


class IBClient(EClient):

    def __init__(self, wrapper):
        EClient.__init__(self, wrapper)


class IBApp(IBWrapper, IBClient):
    def __init__(self, ipaddress, portid, traders=[], secondaryTrader=None):
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
    chatbot = ChatBot()

    twlo_trader = RaivoTrader('TWLO', units=64, chatbot=chatbot, last_5_day_max=255.26, last_5_day_min=240.82, delta=0.4)
    fb_trader = RaivoTrader('FB', units=76, chatbot=chatbot, last_5_day_max=264.00, last_5_day_min=259.82, delta=0.4)
    nvda_trader = RaivoTrader('NVDA', units=44, chatbot=chatbot, last_5_day_max=500.26, last_5_day_min=455, delta=0.4)

    bmw_contract = Contract()
    bmw_contract.symbol = 'BMW'
    bmw_contract.secType = 'STK'
    bmw_contract.exchange = 'IBIS'
    bmw_contract.currency = 'EUR'

    tradingHoursStart = datetime.now().replace(hour=10, minute=00, second=0)
    tradingHoursEnd = datetime.now().replace(hour=19, minute=00, second=0)
    bmw_trader = RaivoTrader(None,
                             contract=bmw_contract,
                             units=365,
                             chatbot=chatbot,
                             last_5_day_max=59.70,
                             last_5_day_min=57.31,
                             tradingHoursStart=tradingHoursStart,
                             tradingHoursEnd=tradingHoursEnd)
    traderList = [
        bmw_trader,
        twlo_trader,
        fb_trader,
 #       nvda_trader
    ]

    tradingIb = IBApp("127.0.0.1", 1234)
    ib = IBApp("127.0.0.1", 7400, traders=traderList, secondaryTrader=tradingIb)
    time.sleep(5)

    for t in traderList:
        logging.warning("RealTimeBars requested for: %s", t.contract.symbol)
        ib.reqTickByTickData(t.tickDataId, t.contract, "MidPoint", 0, False)
        ib.reqRealTimeBars(t.reqId, t.contract, 30, "TRADES", False, [])
