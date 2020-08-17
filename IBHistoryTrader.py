from datetime import datetime

import pandas as pd
from ibapi.common import RealTimeBar

from traders.ma.history_trader import HistoryTrader

df = pd.read_csv("history/2020.08.10 14-30-54-SOXL-TRADES 3 D 30 secs.csv", index_col=0)
df.index = pd.to_datetime(df.index)
df['date'] = df.index.date
unique_dates = df['date'].unique()
current_money = 0
day_data = []


def to_integer(dt_time):
    return 10000 * dt_time.year + 100 * dt_time.month + dt_time.day


for unique_date in unique_dates:
    df_day = df[df['date'] == unique_date]
    first_row = df_day.head(1)
    last_row = df_day.tail(1)

    first_time = first_row.index.values[0]
    last_time = last_row.index.values[0]

    day_trader = HistoryTrader(symbol="SOXL", units=100, tradingHoursStart=first_time, tradingHoursEnd=last_time)

    for index, row in df_day.iterrows():
        unix_seconds = int((index - datetime(1970, 1, 1)).total_seconds())
        bar = RealTimeBar(unix_seconds, close=row['close'])
        day_trader.set_mocked_now(index)
        day_trader.newBar(bar)
    print("Earned", day_trader.earned)
    day_data.append([unique_date, day_trader.earned])
    current_money += day_trader.earned
df_earned = pd.DataFrame(day_data, columns=['Date', 'Earned'])
df_earned.to_excel("HistoryTest.xlsx")
datetime.now().time()