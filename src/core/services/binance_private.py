import hashlib
import hmac
import time
from urllib.parse import urlencode
import json

import requests

from src.config.settings import settings


class BinanceService:
  def __init__(self):
    self.base_url = "https://fapi.binance.com"
    self.api_key = settings.pocket_api_key
    self.api_secret = settings.pocket_api_secret
    self.session = requests.Session()
    self.precision = {
      "BTCUSDT": (3, 1),
      "ETHUSDT": (3, 2),
      "BNBUSDT": (2, 1)
    }
    self.min_amount = json.loads(f"{{{settings.min_amount_for_operation}}}")

  def _sign(self, params: dict) -> str:
    qs = urlencode(params)
    return hmac.new(
      self.api_secret.encode(),
      qs.encode(),
      hashlib.sha256
    ).hexdigest()

  def _request(self, method: str, endpoint: str, params: dict = None):
    params = dict(params or {})
    params["timestamp"] = int(time.time() * 1000)
    params["recvWindow"] = 5000
    params["signature"] = self._sign(params)

    response = self.session.request(
      method,
      f"{self.base_url}{endpoint}",
      headers={"X-MBX-APIKEY": self.api_key},
      params=params,
      timeout=10
    )

    data = response.json() if response.text else {}
    if response.status_code >= 400:
      raise Exception(f"Binance error {response.status_code}: {data}")

    return data

  def _ensure_isolated(self, symbol: str):
    """Asegura que el símbolo esté en modo ISOLATED."""
    try:
      self._request(
        "POST",
        "/fapi/v1/marginType",
        {"symbol": symbol, "marginType": "ISOLATED"}
      )
    except Exception as e:
      if "No need to change margin type" not in str(e):
        raise

  def open_limit_order(
    self,
    symbol: str,
    side: str,
    quantity: float,
    price: float
  ):
    """Abre una LIMIT en ISOLATED y retorna (orderId, status)."""
    self._ensure_isolated(symbol)

    qty_prec, price_prec = self.precision.get(symbol, (3, 2))
    qty = round(quantity, qty_prec)
    price = round(price, price_prec)

    result = self._request("POST", "/fapi/v1/order", {
      "symbol": symbol,
      "side": side,
      "type": "LIMIT",
      "quantity": qty,
      "price": price,
      "timeInForce": "GTC"
    })

    return result.get("orderId"), result.get("status")

  def get_order_status(self, symbol: str, order_id: str):
    """Obtiene el estado de una orden de entrada."""
    result = self._request("GET", "/fapi/v1/order", {
      "symbol": symbol,
      "orderId": order_id
    })
    return result.get("status")

  def has_open_position(self, symbol: str) -> bool:
    """Indica si Binance mantiene una posición con cantidad distinta de cero."""
    positions = self._request(
      "GET",
      "/fapi/v2/positionRisk",
      {"symbol": symbol}
    )

    if isinstance(positions, dict):
      positions = [positions]

    return any(
      abs(float(position.get("positionAmt", 0))) > 0
      for position in positions
    )

  def has_open_order(self, symbol: str) -> bool:
    """Indica si Binance tiene una orden regular abierta para el símbolo."""
    orders = self._request(
      "GET",
      "/fapi/v1/openOrders",
      {"symbol": symbol}
    )
    return bool(orders)

  def has_active_trade(self, symbol: str) -> bool:
    """Protección adicional para no duplicar operaciones del mismo símbolo."""
    return self.has_open_position(symbol) or self.has_open_order(symbol)

  def close_position(self, symbol: str, side: str):
    """Cierra posición con orden MARKET."""
    close_side = "SELL" if side == "BUY" else "BUY"
    qty = self.min_amount.get(symbol, 0.001)
    qty_prec, _ = self.precision.get(symbol, (3, 2))
    qty = round(qty, qty_prec)

    self._request("POST", "/fapi/v1/order", {
      "symbol": symbol,
      "side": close_side,
      "type": "MARKET",
      "quantity": qty,
      "reduceOnly": "true"
    })

  def cancel_order(self, symbol: str, order_id: str):
    """Cancela una orden."""
    self._request("DELETE", "/fapi/v1/order", {
      "symbol": symbol,
      "orderId": order_id
    })

  def set_tp_sl(
    self,
    symbol: str,
    side: str,
    qty: float,
    tp: float,
    sl: float
  ):
    """Crea TP/SL y retorna sus algoId."""
    _, price_prec = self.precision.get(symbol, (3, 2))

    tp = round(tp, price_prec)
    sl = round(sl, price_prec)
    close_side = "SELL" if side == "BUY" else "BUY"

    tp_algo_id = None
    sl_algo_id = None

    try:
      result = self._request("POST", "/fapi/v1/algoOrder", {
        "algoType": "CONDITIONAL",
        "symbol": symbol,
        "side": close_side,
        "type": "TAKE_PROFIT_MARKET",
        "triggerPrice": tp,
        "closePosition": "true",
        "workingType": "CONTRACT_PRICE"
      })

      tp_algo_id = result.get("algoId")

    except Exception as e:
      print(f"Error creando TP para {symbol}: {e}")

      if "-2021" in str(e):
        print(f"TP ya alcanzado, cerrando posición {symbol}")
        self.close_position(symbol, side)
        return None, None

    try:
      result = self._request("POST", "/fapi/v1/algoOrder", {
        "algoType": "CONDITIONAL",
        "symbol": symbol,
        "side": close_side,
        "type": "STOP_MARKET",
        "triggerPrice": sl,
        "closePosition": "true",
        "workingType": "CONTRACT_PRICE"
      })

      sl_algo_id = result.get("algoId")

    except Exception as e:
      print(f"Error creando SL para {symbol}: {e}")

      if "-2021" in str(e):
        print(f"SL ya alcanzado, cerrando posición {symbol}")
        self.close_position(symbol, side)

    return tp_algo_id, sl_algo_id

  def get_algo_order(self, algo_id: int):
    """Obtiene una orden condicional TP/SL por algoId."""
    return self._request(
      "GET",
      "/fapi/v1/algoOrder",
      {
        "algoId": algo_id
      }
    )