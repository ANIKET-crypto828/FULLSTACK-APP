import config
import sqlite3
import pandas as pd
import pandas
import csv
import alpaca_trade_api as tradeapi
from datetime import datetime, timedelta
from polygon import RESTClient

pandas.set_option('display.max_rows', -1)

connection = sqlite3.connect(config.DB_FILE)
connection.row_factory = sqlite3.Row
cursor = connection.cursor()

symbols = []
stocks_ids = {} 

with open('qqq.csv') as f:
  reader = csv.reader(f)
  for line in reader:
    symbols.append(line[1])

cursor.execute("""
    SELECT * FROM stock
""")
stocks = cursor.fetchall()

for stock in stocks:
  symbol = stock['symbol']
  stocks_ids[symbol] = stock['id']

for symbol in symbols:
    start_date = datetime(2025, 1, 6).date()
    end_date_range = datetime(2025, 10, 11).date()
    

    while start_date < end_date_range:
       end_date = start_date + timedelta(days=4)

       print(f"=== Fetching minute bars {start_date}-{end_date} for {symbol}")
       api = tradeapi.REST(config.API_KEY, config.SECRET_KEY, config.API_URL)

       client = RESTClient("cPlswRb3a9YgCfpGVGYsSOOJWw5QllrJ")

       minutes = client.get_aggs(
       symbol,
       multiplier=1,
       timespan="minute",
       from_="2025-01-01",
       to="2025-10-11"
       )
       minutes = minutes.resample('1min').ffill()
       print(minutes)

#df = pd.DataFrame([a.__dict__ for a in minutes])
#print(df.head())"""

       for index, row in minutes.iterrows():
          cursor.execute("""
            INSERT INTO stock_price_minute (stock_id, datetime, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (stocks_ids[symbol], index.tz_localize(None).isoformat(), row['open'], row['high'], row['low'], row['close'], row['volume'],))

          start_date = start_date + timedelta(days=7)
  
  
connection.commit()