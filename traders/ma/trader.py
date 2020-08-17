import pandas
from ibapi.client import *
from ibapi.contract import *

import datetime
import numpy as np
from helpers.ibhelper import us_stocks_contract
from helpers.threading import synchronized_method

import logging


class Trader:
    def __init__(self,
                 symbol=None,
                 units=None,
                 contract: Contract = None,
                 mas=None,
                 max_data_size=200,
                 bar_size=60,
                 delta=0.0012,
                 tradingHoursStart=None,
                 tradingHoursEnd=None,
                 chatbot=None):
        self.orders = []
        if chatbot is not None:
            self.chatbot = chatbot
        self.tradingHoursStart = tradingHoursStart
        if self.tradingHoursStart is None:
            self.tradingHoursStart = self.get_now().replace(hour=16, minute=30, second=1)

        self.tradingHoursEnd = tradingHoursEnd
        if self.tradingHoursEnd is None:
            self.tradingHoursEnd = self.get_now().replace(hour=23, minute=00, second=0)

        self.last_response_time = None
        self.previousOrderId = None
        self.traderApp = None
        if mas is None:
            mas = [
                {"name": "SMA20", "period": 20, "type": "SMA"},
                {"name": "SMA6", "period": 9, "type": "SMA"}
            ]
        self.mas = mas
        self.contract = contract
        if symbol is not None:
            self.contract = us_stocks_contract(symbol)
        self.last_buy_price = 0
        self.last_sell_price = 0
        self.current_state = None
        self.units = units
        self.current_price = 0

        self.max_data_size = max_data_size
        self.bar_size = bar_size
        self.delta_percentage = delta
        self.df = None

    def newBar(self, bar: RealTimeBar):
        logging.warning("State %s\t%s. Close: %s", self.current_state, self.contract.symbol, bar.close)
        if self.df is None:
            self.df = self.createDf(bar)
        elif self.last_response_time is None or bar.time - self.last_response_time >= self.bar_size:
            self.df = self.df.append(self.createDf(bar))
        self.trade()
        if len(self.df.axes[0]) >= self.max_data_size:
            self.df = self.df.iloc[1:]

    def createDf(self, bar):
        data_frame = pandas.DataFrame([[bar.time, bar.close]], columns=['time', 'close'])
        data_frame.set_index('time', inplace=True)
        return data_frame

    @synchronized_method
    def calculateMAsAndSentiment(self):
        for ma in self.mas:
            if ma['type'] is 'SMA':
                self.df[ma['name']] = self.df['close'].rolling(ma['period']).mean()
            if ma['type'] is 'EMA':
                self.df[ma['name']] = self.df['close'].ewm(ma['period']).mean()
        self.df['sentiment'] = self.df.apply(self.comparePrices, axis=1)
        last_row = self.df.tail(1)
        last_sentiment = last_row.iloc[0]['sentiment']
        last_price = last_row.iloc[0]['close']
        last_time = last_row.index.values[0]
        return last_sentiment, last_price, last_time

    def comparePrices(self, row):
        if np.isnan(row['SMA6']):
            return 'HOLD'
        if row['close'] > row['SMA6']:
            return 'LONG'
        else:
            return 'SHORT'

    @synchronized_method
    def trade(self):
        last_state, self.current_price, self.last_response_time = self.calculateMAsAndSentiment()
        if self.current_state is not last_state and last_state is not 'HOLD':
            time_remaining = (self.tradingHoursEnd - self.get_now()).total_seconds() / 60.0
            print(self.df)
            print("CURRENT", self.current_state, "LAST", last_state, self.current_price, self.isTradingHours(), self.canBuy(), self.canSell())
            if self.isTradingHours() and time_remaining < 2:
                if self.current_state is 'LONG':
                    self.sell(price=self.current_price)
                elif self.get_now() > self.tradingHoursEnd:
                    print("End of day. Trader EXIT")
                    self.traderApp.disconnect()
                    raise SystemExit
            elif self.isTradingHours() and last_state is 'LONG' and self.current_state is not 'LONG' and self.canBuy():
                self.buy(price=self.current_price)
            elif self.isTradingHours() and last_state is 'SHORT' and self.current_state is 'LONG' and self.canSell():
                self.sell(price=self.current_price)

    def get_now(self):
        return datetime.datetime.now()

    def buy(self, price=None):

        self.last_buy_price = price
        order = Order()
        order.action = 'BUY'
        order.orderType = "MKT"
        order.totalQuantity = self.units

        self.openOrder(order)
        self.current_state = 'LONG'
        print("Buy", price)

    def sell(self, price=None):
        self.last_sell_price = price
        order = Order()
        order.action = 'SELL'
        order.orderType = "MKT"
        order.totalQuantity = self.units

        self.openOrder(order)
        self.current_state = 'SHORT'
        print("Sell", price)

    def isTradingHours(self):
        return self.tradingHoursStart <= self.get_now() < self.tradingHoursEnd

    def canBuy(self):
        print("Last SELL price", self.last_sell_price)
        return (abs(self.last_sell_price - self.current_price) * 100 / self.current_price) >= self.delta_percentage

    def canSell(self):
        print("Last BUY price", self.last_buy_price)
        return (abs(self.last_buy_price - self.current_price) * 100 / self.current_price) >= self.delta_percentage

    def openOrder(self, order):
        orderId = self.traderApp.nextorderId
        self.traderApp.placeOrder(orderId, self.contract, order)
        self.previousOrderId = orderId
        self.orders.append({'orderId': orderId, 'action': order.action})
        self.traderApp.nextorderId = orderId + 1

    def hasOrderUpdate(self, orderId, status, filled, avgFillPrice, lastFillPrice):
        for order in self.orders:
            if order['orderId'] is orderId and status is 'Filled':
                order_price = None
                if avgFillPrice is not None:
                    order_price = avgFillPrice
                if lastFillPrice is not None:
                    order_price = avgFillPrice
                if order['action'] is 'BUY':
                    if order_price is not None:
                        self.last_buy_price = order_price
                    self.chatbot.send(
                        "BOUGHT\nSYMBOL: " + self.contract.symbol + "\nPRICE: " + str(self.last_buy_price))
                if order['action'] is 'SELL':
                    if order_price is not None:
                        self.last_sell_price = order_price
                    earned = (order_price - self.last_buy_price) * self.units
                    self.chatbot.send(
                        "SOLD\nSYMBOL: " + self.contract.symbol + "\nPRICE: " + str(
                            self.last_sell_price) + "\nEARNED: " + str(earned))
