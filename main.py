import sqlite3, config

from fastapi.responses import RedirectResponse
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.templating import Jinja2Templates
from datetime import datetime, date

current_date = datetime.now().strftime("%Y-%m-%d")

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/")
def index(request: Request):
    stock_filter = request.query_params.get("filter", False)

    connection = sqlite3.connect(config.DB_FILE)

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    if stock_filter == "new_closing_highs":
        cursor.execute("""
        select * from (
                select symbol, name, stock_id, max(close), date
                from stock_price join stock on stock.id = stock_price.stock_id
                group by stock_id
                order by symbol
            ) where date = (select max(date) from stock_price)
        """, (date.today().isoformat(),))
    elif stock_filter == "new_closing_lows":
             cursor.execute("""
        select * from (
                select symbol, name, stock_id, min(close), date
                from stock_price join stock on stock.id = stock_price.stock_id
                group by stock_id
                order by symbol
            ) where date = (select max(date) from stock_price)
        """, (date.today().isoformat(),))
    else:
        cursor.execute("""
            SELECT id, symbol, name FROM stock ORDER BY symbol
        """)

    rows = cursor.fetchall()

    current_date = date.today().isoformat()
    cursor.execute("""
        SELECT symbol, rsi_14, sma_20, sma_50, close
        FROM stock join stock_price on stock_price.stock_id = stock.id
        WHERE date = (select max(date) from stock_price)
    """)

    indicator_rows = cursor.fetchall()
    indicator_values = {}

    for row in indicator_rows:
        indicator_values[row['symbol']] = row

    print(indicator_values) 

    return templates.TemplateResponse("index.html", {"request": request, "stocks": rows, "indicator_values": indicator_values})

@app.get("/stock/{symbol}")
def stock_detail(request: Request, symbol: str):
    connection = sqlite3.connect(config.DB_FILE)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    # Fetch strategies
    cursor.execute("""
        SELECT * FROM strategy
    """)
    strategies = cursor.fetchall()

    # Fetch stock row first
    cursor.execute("""
        SELECT id, symbol, name FROM stock WHERE symbol = ?
    """, (symbol,))
    row = cursor.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Fetch prices
    cursor.execute("""
        SELECT * FROM stock_price WHERE stock_id = ? ORDER BY date DESC
    """, (row['id'],))
    prices = cursor.fetchall()

    return templates.TemplateResponse(
        "stock_detail.html",
        {"request": request, "stock": row, "bars": prices, "strategies": strategies}
    )

@app.post("/apply_strategy")
def apply_strategy(strategy_id: int = Form(...), stock_id: int = Form(...)):
    connection = sqlite3.connect(config.DB_FILE)
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO stock_strategy (stock_id, strategy_id)
        VALUES (?, ?)
    """, (stock_id, strategy_id))

    connection.commit()

    return RedirectResponse(url=f"/strategy/{strategy_id}", status_code=303, headers={"message": "Strategy applied successfully"})

@app.get("/strategy/{strategy_id}")
def strategy(request: Request, strategy_id: int):
    connection = sqlite3.connect(config.DB_FILE)
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name FROM strategy WHERE id = ?
    """, (strategy_id,))

    strategy = cursor.fetchone()

    stocks = cursor.fetchall()

    return templates.TemplateResponse(
        "strategy.html",
        {"request": request, "strategy": strategy, "stocks": stocks}
    )