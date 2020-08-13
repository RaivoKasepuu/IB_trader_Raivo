import pandas
from ibapi.client import *
from ibapi.contract import *

import datetime
import numpy as np
from helpers.ibhelper import us_stocks_contract
from helpers.threading import synchronized_method
from message.chatbot import ChatBot


class Trader:
    def __init__(self,
                 symbol=None,
                 units=None,
                 contract: Contract = None,
                 mas=None,
                 max_data_size=400,
                 bar_size=60,
                 delta=0.0012,
                 tradingHoursStart=None,
                 tradingHoursEnd=None,
                 df=None):
        self.orderDataDf = None
        self.chatbot = ChatBot()
        self.tradingHoursStart = tradingHoursStart
        if self.tradingHoursStart is None:
            self.tradingHoursStart = self.get_now().replace(hour=16, minute=30, second=1)

        self.tradingHoursEnd = tradingHoursEnd
        if self.tradingHoursEnd is None:
            self.tradingHoursEnd = self.get_now().replace(hour=23, minute=00, second=0)

        self.last_response_time = None
        self.previousOrderId = None
        self.traderApp = None
        self.orderData = []
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
        self.last_price = 0

        self.max_data_size = max_data_size
        self.bar_size = bar_size
        self.delta_percentage = delta
        self.df = df

    def newBar(self, bar: RealTimeBar):
        print(self.current_state, self.contract.symbol, bar)
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
        last_state, self.last_price, self.last_response_time = self.calculateMAsAndSentiment()
        if self.current_state is not last_state and last_state is not 'HOLD':
            time_remaining = (self.tradingHoursEnd - self.get_now()).total_seconds() / 60.0
            if self.isTradingHours() and time_remaining < 2:
                if self.current_state is 'LONG':
                    self.sell(price=self.last_price)
                elif self.get_now() > self.tradingHoursEnd:
                    print("End of day. Trader EXIT")
                    self.traderApp.disconnect()
                    raise SystemExit
            elif self.isTradingHours() and last_state is 'LONG' and self.current_state is not 'LONG' and self.canBuy():
                self.buy(price=self.last_price)
            elif self.isTradingHours() and last_state is 'SHORT' and self.current_state is 'LONG' and self.canSell():
                self.sell(price=self.last_price)

    def get_now(self):
        return datetime.datetime.now()

    def buy(self, price=None):

        self.last_buy_price = price
        order = Order()
        order.action = 'BUY'
        order.orderType = "MKT"
        order.totalQuantity = self.units

        self.traderApp.placeOrder(self.traderApp.nextorderId, self.contract, order)
        self.previousOrderId = self.traderApp.nextorderId
        self.traderApp.nextorderId += 1

        self.current_state = 'LONG'

        self.writeCsv([self.get_now(), 'BUY', price])
        print("Buy", price)
        self.chatbot.send("BOUGHT\nSYMBOL: " + self.contract.symbol + "\nPRICE: " + str(price))

    def sell(self, price=None):
        earned = (price - self.last_buy_price) * self.units
        self.last_sell_price = price
        order = Order()
        order.action = 'SELL'
        order.orderType = "MKT"
        order.totalQuantity = self.units

        self.traderApp.placeOrder(self.traderApp.nextorderId, self.contract, order)
        self.previousOrderId = self.traderApp.nextorderId
        self.traderApp.nextorderId += 1

        self.current_state = 'SHORT'

        self.writeCsv([self.get_now(), 'SELL', price])
        print("Sell", price)
        self.chatbot.send(
            "SOLD\nSYMBOL: " + self.contract.symbol + "\nPRICE: " + str(price) + "\nEARNED: " + str(earned))

    def writeCsv(self, orderData):

        self.orderData.append(orderData)
        self.orderDataDf = pandas.DataFrame(self.orderData, columns=['time', 'action', 'price'])
        self.orderDataDf.to_csv(self.contract.symbol + '.csv')

    def isTradingHours(self):
        return self.tradingHoursStart <= self.get_now() < self.tradingHoursEnd

    def canBuy(self):
        return True
        # return (abs(self.last_sell_price - self.last_price) / self.last_price) >= self.delta_percentage

    def canSell(self):
        return (abs(self.last_buy_price - self.last_price) / self.last_price) >= self.delta_percentage
