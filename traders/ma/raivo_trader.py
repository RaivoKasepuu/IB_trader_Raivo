import numpy as np

from traders.ma.trader import Trader


class RaivoTrader(Trader):
    def __init__(self,
                 symbol=None,
                 units=None,
                 last_5_day_min=None,
                 last_5_day_max=None,
                 mas=[{"name": "SMA9", "period": 9, "type": "SMA"}],
                 tradingHoursStart=None,
                 tradingHoursEnd=None,
                 chatbot=None):
        super().__init__(symbol,
                         units,
                         delta=0.1,
                         mas=mas,
                         tradingHoursStart=tradingHoursStart,
                         tradingHoursEnd=tradingHoursEnd,
                         chatbot=chatbot)
        self.last_5_day_min = last_5_day_min
        self.last_5_day_max = last_5_day_max
        self.long_limit = last_5_day_min + 0.8 * (last_5_day_max-last_5_day_min)
        self.short_limit = last_5_day_min + 0.2 * (last_5_day_max-last_5_day_min)

    def comparePrices(self, row):
        if np.isnan(row['SMA9']):
            return 'HOLD'
        if row['close'] > self.long_limit:
            return 'SHORT'
        elif row['close'] < self.short_limit:
            return 'LONG'
        elif row['close'] > row['SMA9']:
            return 'LONG'
        else:
            return 'SHORT'

    def canBuy(self):
        return abs(self.last_sell_price - (self.delta_percentage*self.last_sell_price)) > self.current_price

    def canSell(self):
        return abs(self.last_buy_price - (self.delta_percentage*self.last_buy_price)) > self.current_price
