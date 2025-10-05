import sqlite3
import pandas as pd
import config, tulipy
import alpaca_trade_api as tradeapi
from datetime import date, datetime
from timezone import is_dst

print(datetime.now())

connection = sqlite3.connect(config.DB_FILE)
connection.row_factory = sqlite3.Row

cursor = connection.cursor()

cursor.execute("""
    select id from strategy where name = 'boilinger_bands'               
""")

strategy_id = cursor.fetchone()['id']

cursor.execute("""
      select symbol, name
      from stock
      join stock_strategy on stock_strategy.stock_id = stock.id
      where stock_strategy.strategy_id = ?
""", (strategy_id,))

stocks = cursor.fetchall()
symbols = [stock['symbol'] for stock in stocks]

current_date = datetime.now().strftime('%Y-%m-%d')  # Use current date instead of hardcoded

"""ny_tz = pytz.timezone('America/New_York')
start_minute_bar = ny_tz.localize(datetime.strptime(f"{current_date} 09:30:00", "%Y-%m-%d %H:%M:%S"))
end_minute_bar = ny_tz.localize(datetime.strptime(f"{current_date} 09:45:00", "%Y-%m-%d %H:%M:%S"))"""


start_minute_bar = f"{current_date} 09:30:00-05:00"
end_minute_bar = f"{current_date} 10:28:00-05:00"

api = tradeapi.REST(config.API_KEY, config.SECRET_KEY, base_url=config.API_URL)

orders = api.list_orders(status='all', after=current_date)
existing_order_symbols = [order.symbol for order in orders if order.status != 'canceled']

messages = []

for symbol in symbols:
    minute_bars = api.polygon.historic_agg_v2(symbol, 1, 'minute', _from=current_date, to=current_date).df
    

    market_open_mask = (minute_bars.index >= start_minute_bar) & (minute_bars.index <= end_minute_bar)
    market_open_bars = minute_bars.loc[market_open_mask]
    print(market_open_bars)

    if len(market_open_bars) >= 20:
        closes = market_open_bars.close.values
        lower, middle, upper = tulipy.bbands(closes, 20, 2)

        current_candle = market_open_bars.iloc[-1]
        previous_candle = market_open_bars.iloc[-2]

        if current_candle.close > lower[-1] and previous_candle.close < lower[-2]:
            print(f"{symbol} Closed above lower boilinger band")
            print(current_candle)

            if symbol not in existing_order_symbols:
                limit_price = current_candle.close

                candle_range = current_candle.high - current_candle.low

                print(f"Placing order for {symbol} at {limit_price}")

                try:
                    api.submit_order(
                        symbol=symbol,
                        side='buy',
                        type='limit',
                        qty='100',
                        time_in_force='day',
                        order_class='bracket',
                        limit_price=limit_price,
                        take_profit=dict(
                            limit_price=limit_price + (candle_range * 3),
                        ),
                        stop_loss=dict(
                            stop_price=previous_candle.low,
                        )
                    )
                except Exception as e:
                    print(f"Error placing order for {symbol}: {e}")
            else:
                print(f"Already an order for {symbol}, skipping")
