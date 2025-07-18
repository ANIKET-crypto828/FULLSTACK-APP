import sqlite3, config
import alpaca_trade_api as tradeapi

connection = sqlite3.connect(config.DB_FILE)
connection.row_factory = sqlite3.Row
cursor = connection.cursor()

cursor.execute("""
    SELECT id, symbol, name FROM stock
""")

rows = cursor.fetchall()
print(f"Found {len(rows)} stocks in database")

# Add these filters when building your symbols list
symbols = []
stock_dict = {}
for row in rows:
    symbol = row['symbol']
    # Skip warrants, preferred shares, and obscure symbols
    if ('/' not in symbol and 
        '.PR' not in symbol and 
        not symbol.endswith('W') and 
        not symbol.endswith('U')):
        symbols.append(symbol)
        stock_dict[symbol] = row['id']

print(f"Processing {len(symbols)} symbols after filtering")

api = tradeapi.REST(config.API_KEY, config.SECRET_KEY, base_url=config.API_URL)

# Test API connection
try:
    account = api.get_account()
    print("Alpaca connection successful. Account status:", account.status)
except Exception as e:
    print("Alpaca connection failed:", str(e))

# Test with a known symbol
try:
    test_bars = api.get_bars('AAPL', '1Day', limit=1)
    print(f"Test AAPL data: {test_bars}")
except Exception as e:
    print(f"Test failed: {str(e)}")

chunk_size = 200
for i in range(0, len(symbols), chunk_size):
    symbol_chunk = symbols[i:i + chunk_size]
    print(f"\nProcessing chunk {i} to {i+chunk_size}: {symbol_chunk}")
    
    try:
        barsets = api.get_bars(symbol_chunk, '1Day')
        print(f"Received data for {len(barsets)} symbols in this chunk")
        
        for symbol in barsets:
            print(f"Processing {symbol} with {len(barsets[symbol])} bars")
            for bar in barsets[symbol]:
                stock_id = stock_dict[symbol]
                cursor.execute("""
                    INSERT INTO stock_price (stock_id, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (stock_id, bar.t.date(), bar.open, bar.high, bar.low, bar.close, bar.volume))
    except Exception as e:
        print(f"Error processing chunk {i}: {str(e)}")
        continue

connection.commit()
print("Data population complete")