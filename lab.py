from src.core.services.binance_private import BinanceService

binance = BinanceService()

# Test: orden LIMIT de compra BTCUSDT al precio actual - 1000 (no se ejecutará)
symbol = "BTCUSDT"
side = "BUY"
qty = binance.min_amount.get(symbol)
price = 50000.0  # Precio bajo para que no se ejecute

print(f"Creando orden: {symbol} {side} qty={qty} price={price}")

try:
  order_id, status = binance.open_limit_order(symbol, side, qty, price)
  print(f"Orden creada! ID: {order_id}, Status: {status}")
except Exception as e:
  print(f"Error: {e}")
