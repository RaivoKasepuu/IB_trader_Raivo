import datetime

import pandas
from ibapi.client import *
from ibapi.contract import *

from helpers.threading import synchronized_method
from traders.ma.trader import Trader


class HistoryTrader(Trader):
    def __init__(self, symbol=None,
                 units=None,
                 tradingHoursStart=None,
                 tradingHoursEnd=None,
                 df=None):
        super().__init__(symbol,
                         units,
                         tradingHoursStart=tradingHoursStart,
                         tradingHoursEnd=tradingHoursEnd)
        self.mocked_now = None
        self.earned = 0

    @synchronized_method
    def trade(self):
        last_state, self.last_price, self.last_response_time = self.calculateMAsAndSentiment()
        if self.current_state is not last_state and last_state is not 'HOLD':
            time_remaining = (self.tradingHoursEnd - self.get_now()).total_seconds() / 60.0
            if self.isTradingHours() and time_remaining < 2:
                if self.current_state is 'LONG':
                    self.sell(price=self.last_price)
                    print("End of day. Trader EXIT")
            elif self.isTradingHours() and last_state is 'LONG' and self.current_state is not 'LONG' and self.canBuy():
                self.buy(price=self.last_price)
            elif self.isTradingHours() and last_state is 'SHORT' and self.current_state is 'LONG' and self.canSell():
                self.sell(price=self.last_price)

    def get_now(self):
        return self.mocked_now

    def calculate_order_fee(self, order_unit_price, amount):
        fee = order_unit_price * amount
        if fee < 7:
            return 7
        return fee

    def buy(self, price=None):

        self.earned += -self.calculate_order_fee(0.2, self.units)
        order = Order()
        order.action = 'BUY'
        order.orderType = "MKT"
        order.totalQuantity = self.units
        if self.previousOrderId:
            order.parentId = self.previousOrderId

        self.current_state = 'LONG'
        print("Buy", price, "Earned", self.earned)

    def sell(self, price=None):
        self.earned += ((price - self.last_buy_price) * self.units) - self.calculate_order_fee(0.2, self.units)
        self.last_sell_price = price
        order = Order()
        order.action = 'SELL'
        order.orderType = "MKT"
        order.totalQuantity = self.units

        self.current_state = 'SHORT'
        print("Sell", price, "Earned", self.earned)

    def canBuy(self):
        return True
        # return (abs(self.last_sell_price - self.last_price) / self.last_price) >= self.delta_percentage

    def canSell(self):
        return True
        #return (abs(self.last_buy_price - self.last_price) / self.last_price) >= self.delta_percentage

    def set_mocked_now(self, index):
        self.mocked_now = index
