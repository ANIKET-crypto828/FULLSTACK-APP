import config, tulipy
import alpaca_trade_api as tradeapi
from helpers import calculate_quantity

api = tradeapi.REST(config.API_KEY, config.SECRET_KEY, base_url=config.API_URL)

"""symbols = ['SPY', 'IWM', 'DIA']

for symbol in symbols:

  quote = api.get_last_quote(symbol)
  
  api.submit_order(
    symbol=symbol,
    qty=1,
    side='buy',
    type='market',
    time_in_force='day',
    qty=calculate_quantity(quote.bidprice),
  )"""

#orders = api.list_orders() 
#positions = api.list_positions()

"""api.submit_order(
  symbol='IWM',
  side='sell',
  qty=57,
  time_in_force='day',
  type='trailing_stop',
  trail_price='0.20'
)

api.submit_order(
  symbol='DIA',
  side='sell',
  qty=5,
  time_in_force='day',
  type='trailing_stop',
  trail_percent='0.70'
)"""

daily_bars = api.polygon.historic_agg_v2('NIO', 1, 'day', _from='2025-10-06', to='2025-11-13')

print(daily_bars)

atr = tulipy.atr(daily_bars.high.values, daily_bars.low.values, daily_bars.close.values, 14)

print(atr)