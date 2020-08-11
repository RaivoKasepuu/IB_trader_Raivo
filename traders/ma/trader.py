import pandas
from ibapi.client import *
from ibapi.contract import *

import numpy as np
from helpers.ibhelper import us_stocks_contract
from helpers.threading import synchronized_method


class Trader:
    def __init__(self,
                 symbol=None,
                 units=None,
                 contract: Contract = None,
                 mas=None,
                 max_data_size=30,
                 bar_size=30,
                 delta=0.0022,
                 df=None):

        self.last_response_time = None
        if mas is None:
            mas = [
                {"name": "SMA26", "period": 26, "type": "SMA"},
                {"name": "SMA9", "period": 9, "type": "SMA"}
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
        print("Symbol", self.contract.symbol, bar)
        if self.df is None:
            self.df = self.createDf(bar)
            self.trade()
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
        last_sentiment = last_row['sentiment']
        last_price = last_row['close']
        last_time = last_row.index
        return last_sentiment, last_price, last_time

    def comparePrices(self, row):
        for ma in self.mas:
            if np.isnan(row[ma['name']]):
                return 'HOLD'
        is_bigger = True
        for ma in self.mas:
            if row['close'] <= row[ma['name']]:
                is_bigger = False
        if is_bigger:
            return 'LONG'
        else:
            return 'SHORT'

    @synchronized_method
    def trade(self):
        last_state, self.last_price, self.last_response_time = self.calculateMAsAndSentiment()
        if self.current_state is not last_state and last_state is not 'HOLD':
            acceptable_delta = self.last_price * self.delta_percentage
            print("Symbol", self.contract.symbol, "\n\n", self.df)
            if self.current_state is 'LONG' and abs(self.last_buy_price - self.last_price) > acceptable_delta:
                self.sell(price=self.last_price)
            if self.current_state is 'SHORT' and abs(self.last_sell_price - self.last_price) > acceptable_delta:
                self.buy(price=self.last_price)

    def buy(self, price=None):
        print("Buy", price)
        print(self.df)

    def sell(self, price=None):
        print("Sell", price)
        print(self.df)
