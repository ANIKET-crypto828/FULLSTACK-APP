import sqlite3
import pandas as pd
import config
import alpaca_trade_api as tradeapi
import smtplib, ssl
from datetime import datetime
import pytz
from timezone import is_dst
from helpers import calculate_quantity

print(datetime.now())

context = ssl.create_default_context()

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

current_date = datetime.now().strftime('%Y-%m-%d')  # Use current date instead of hardcoded

"""ny_tz = pytz.timezone('America/New_York')
start_minute_bar = ny_tz.localize(datetime.strptime(f"{current_date} 09:30:00", "%Y-%m-%d %H:%M:%S"))
end_minute_bar = ny_tz.localize(datetime.strptime(f"{current_date} 09:45:00", "%Y-%m-%d %H:%M:%S"))"""

if is_dst():
    start_minute_bar = f"{current_date} 09:30:00-05:00"
    end_minute_bar = f"{current_date} 09:45:00-05:00"
else:
    start_minute_bar = f"{current_date} 09:30:00-04:00"
    end_minute_bar = f"{current_date} 09:45:00-04:00"

api = tradeapi.REST(config.API_KEY, config.SECRET_KEY, base_url=config.API_URL)

orders = api.list_orders(status='all', after=current_date)
existing_order_symbols = [order.symbol for order in orders if order.status != 'canceled']

messages = []

for symbol in symbols:
    try:
        print(f"\nProcessing {symbol}")
        
        # Get minute bars with error handling
        try:
            minute_bars = api.get_bars(
                symbol,
                timeframe='1Min',
                start=current_date,
                end=current_date,
                adjustment='raw'
            ).df
        except Exception as e:
            print(f"Error getting bars for {symbol}: {e}")
            continue

        # Skip if no data returned
        if minute_bars.empty:
            print(f"No data returned for {symbol}")
            continue

        # Handle timezone and index
        if not isinstance(minute_bars.index, pd.DatetimeIndex):
            minute_bars.index = pd.to_datetime(minute_bars.index)
        
        if minute_bars.index.tz is None:
            minute_bars.index = minute_bars.index.tz_localize('UTC').tz_convert('America/New_York')
        else:
            minute_bars.index = minute_bars.index.tz_convert('America/New_York')

        # Verify required columns exist
        required_columns = ['open', 'high', 'low', 'close']
        missing_columns = [col for col in required_columns if col not in minute_bars.columns]
        if missing_columns:
            print(f"Missing columns {missing_columns} for {symbol}, skipping")
            continue

        # Convert to numeric and drop NA values
        for col in required_columns:
            minute_bars[col] = pd.to_numeric(minute_bars[col], errors='coerce')
        minute_bars = minute_bars.dropna(subset=required_columns)

        opening_range_mask = (minute_bars.index >= start_minute_bar) & (minute_bars.index <= end_minute_bar)
        opening_range_bars = minute_bars.loc[opening_range_mask]
        
        if opening_range_bars.empty:
            print(f"No data for {symbol} in opening range (09:30-09:45)")
            continue

        opening_range_low = opening_range_bars['low'].min()
        opening_range_high = opening_range_bars['high'].max()
        opening_range = opening_range_high - opening_range_low

        after_opening_range_mask = (minute_bars.index > end_minute_bar)
        after_opening_range_bars = minute_bars.loc[after_opening_range_mask]

        after_opening_range_breakout = after_opening_range_bars[
            after_opening_range_bars['close'] > opening_range_high
        ]

        if not after_opening_range_breakout.empty:
            if symbol not in existing_order_symbols:
                limit_price = round(float(after_opening_range_breakout.iloc[0]['close']), 2)
                take_profit_price = round(limit_price + opening_range, 2)
                stop_loss_price = round(limit_price - opening_range, 2)

                messages.append(f"Placing order for {symbol} at {limit_price}, closed_above {opening_range_high} \n\n {after_opening_range_breakout.iloc[0]}\n\n")

                print(f"Placing order for {symbol} at {limit_price}, closed_above {opening_range_high} at {after_opening_range_breakout.iloc[0]}")
                print(f"Take profit: {take_profit_price}, Stop loss: {stop_loss_price}")

                try:
                    api.submit_order(
                        symbol=symbol,
                        side='buy',
                        type='limit',
                        qty=calculate_quantity(limit_price),
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
                except Exception as e:
                    print(f"Error placing order for {symbol}: {e}")
            else:
                print(f"Already an order for {symbol}, skipping")
                
    except Exception as e:
        print(f"Error processing {symbol}: {str(e)}")

print(messages)

with smtplib.SMTP_SSL(config.EMAIL_HOST, config.EMAIL_PORT, context=context) as server:
    server.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)

    email_message = f"Subject: Trade Notifications for {current_date}\n\n"
    email_message += "\n".join(messages)

    server.sendmail(
        config.EMAIL_ADDRESS,
        config.EMAIL_ADDRESS,
        email_message
    )
    server.sendmail(
        config.EMAIL_ADDRESS,
        config.EMAIL_SMS,
        email_message
    )