import sqlite3
import pandas as pd
import config
import alpaca_trade_api as tradeapi
import datetime as date

connection = sqlite3.connect(config.DB_FILE)
connection.row_factory = sqlite3.Row

cursor = connection.cursor()

cursor.execute("""
    select id from strategy where name = 'opening_range_breakout'               
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

api = tradeapi.REST(config.API_KEY, config.SECRET_KEY, base_url= config.API_URL)

orders = api.list_orders()
existing_order_symbols = [order.symbol for order in orders]
current_date = '2024-10-29'
start_minute_bar = f"{current_date} 09:30:00-04:00"
end_minute_bar = f"{current_date} 09:45:00-04:00"

for symbol in symbols:
    minute_bars = api.get_bars(
        symbol,
        timeframe='1Min',
        start=current_date,
        end=current_date,
        adjustment='raw'
    ).df

    # Ensure the index is a DatetimeIndex based on the 'timestamp' column
    if 'timestamp' in minute_bars.columns:
        minute_bars['timestamp'] = pd.to_datetime(minute_bars['timestamp'])
        minute_bars = minute_bars.set_index('timestamp')

    print(symbol)
    opening_range_mask = (minute_bars.index >= start_minute_bar) & (minute_bars.index <= end_minute_bar)
    opening_range_bars = minute_bars.loc[opening_range_mask]
    print(opening_range_bars)
    opening_range_low = opening_range_bars['low'].min()
    opening_range_high = opening_range_bars['high'].max()
    opening_range = opening_range_high - opening_range_low

    print(opening_range_low)
    print(opening_range_high)
    print(opening_range)

    after_opening_range_mask = (minute_bars.index >= end_minute_bar)
    after_opening_range_bars = minute_bars.loc[after_opening_range_mask]

    print(after_opening_range_bars)

    after_opening_range_breakout = after_opening_range_bars[after_opening_range_bars['close'] > opening_range_high]

    if not after_opening_range_breakout.empty:
        if symbol not in existing_order_symbols:
            limit_price = round(after_opening_range_breakout.iloc[0]['close'], 2)
            take_profit_price = round(limit_price + opening_range, 2)
            stop_loss_price = round(limit_price - opening_range, 2)

            print(f"placing order for {symbol} at {limit_price}, closed_above {opening_range_high} at {after_opening_range_breakout.iloc[0]}")

            api.submit_order(
                symbol=symbol,
                side='buy',
                type='limit',
                qty='100',
                time_in_force='day',
                order_class='bracket',
                limit_price=limit_price,
                take_profit=dict(
                    limit_price=take_profit_price,
                ),
                stop_loss=dict(
                    stop_price=stop_loss_price
                )
            )
        else:
            print(f"Already an order for {symbol}, skipping")