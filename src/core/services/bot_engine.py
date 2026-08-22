from asyncio import sleep
from datetime import datetime, timedelta
from .telegram_notification import TelegramNotificationService
from .market_analysis_service import MarketAnalysisService
from .repositories import DatasetRepository, DecisionRepository
from .binance_private import BinanceService
from ..database import DatabaseSession
from .model import ModelService
from src.config.settings import settings

# 3:1 ratio -> 2% TP, 0.67% SL
TP_PCT = 0.02
SL_PCT = 0.0067
MIN_OPP_PROB = 0.57  # 57% mínimo para operar

class BotEngineService:
  def __init__(self):
    self.market_service = MarketAnalysisService()
    self.dataset_repo = DatasetRepository()
    self.decision_repo = DecisionRepository()
    self.opp_model = ModelService("./models/trade_opportunity_model.pkl")
    self.dir_model = ModelService("./models/trade_direction_model.pkl")
    self.telegram = TelegramNotificationService('Signal IA Bot', settings.telegram_signal_bot_token)
    self.binance = BinanceService()
    self.chat_id = "8534189049"

  async def run_cycle(self, symbol: str, interval: str):
    async with DatabaseSession() as db:
      # Verificar si ya hay orden activa para este symbol
      if await self.decision_repo.has_active_order(db, symbol):
        return
      
      # Obtener indicadores
      klines_df, _ = self.market_service.get_klines_from_date_df(symbol, interval, None, 501)
      indicators = self.market_service.calculate_symbol_indicators(klines_df[:-1])
      indicators["symbol"] = symbol
      indicators["timeframe"] = interval
      
      await sleep(10)
      dataset = await self.dataset_repo.create_dataset(db, indicators)
      
      # Modelo 1: ¿Operar?
      _, opp_probs = self.opp_model.predict(indicators)
      opp_prob = opp_probs[1]  # prob de operar (clase 1)
      
      if opp_prob < MIN_OPP_PROB:
        return
      
      # Modelo 2: ¿Long o Short?
      _, dir_probs = self.dir_model.predict(indicators)
      short_prob, long_prob = dir_probs[0], dir_probs[1]  # 0=short, 1=long
      
      if short_prob > long_prob:
        side, dir_prob = "SELL", short_prob
      else:
        side, dir_prob = "BUY", long_prob
      
      # Si la probabilidad de dirección es baja, rechazar y alertar
      if dir_prob < 0.5:
        self.telegram.send_trade_rejected(self.chat_id, symbol, interval, opp_prob, dir_prob, side)
        return

      current_price = self.market_service.get_current_price_symbol(symbol)
      if (side == "BUY" and current_price > indicators["c_close"]) or (side == "SELL" and current_price < indicators["c_close"]):
        entry = indicators["c_close"]
      else:
        entry = current_price

      if side == "BUY":
        tp = round(entry * (1 + TP_PCT), 2)
        sl = round(entry * (1 - SL_PCT), 2)
      else:
        tp = round(entry * (1 - TP_PCT), 2)
        sl = round(entry * (1 + SL_PCT), 2)
      
      # Crear decision PLANNED (sin TP/SL aún)
      decision = await self.decision_repo.create_decision(db, {
        "dataset_id": dataset.id,
        "status": "PLANNED",
        "side": side,
        "entry_price": entry,
        "tp_price": tp,
        "sl_price": sl,
        "opportunity_prob": opp_prob,
        "direction_prob": dir_prob,
      })
      
      # Crear orden LIMIT
      try:
        qty = self.binance.min_amount.get(symbol, 0.001)
        order_id, status = self.binance.open_limit_order(symbol, side, qty, entry)
        await self.decision_repo.update_status(db, decision.id, "PENDING", str(order_id))
        
        # Si la orden ya está FILLED, crear TP/SL
        if status == "FILLED":
          self.binance.set_tp_sl(symbol, side, qty, tp, sl)
          await self.decision_repo.update_status(db, decision.id, "OPEN", str(order_id))
          self.telegram.send_trade_opened(self.chat_id, symbol, side, entry, tp, sl, opp_prob, dir_prob, order_id)
      except Exception as e:
        print(f"Error abriendo orden: {e}")

  async def check_pending_orders(self):
    """Verifica órdenes PENDING y crea TP/SL si están FILLED"""
    async with DatabaseSession() as db:
      pending = await self.decision_repo.get_decision_by_status(db, "PENDING")
      for decision, symbol in pending:
        try:
          status = self.binance.get_order_status(symbol, decision.ref_number)
          if status == "FILLED":
            qty = self.binance.min_amount.get(symbol, 0.001)
            self.binance.set_tp_sl(symbol, decision.side, qty, decision.tp_price, decision.sl_price)
            await self.decision_repo.update_status(db, decision.id, "OPEN")
            self.telegram.send_trade_opened(
              self.chat_id, symbol, decision.side, decision.entry_price,
              decision.tp_price, decision.sl_price, decision.opportunity_prob,
              decision.direction_prob, decision.ref_number
            )
          elif status in ["CANCELED", "EXPIRED", "REJECTED"]:
            await self.decision_repo.update_status(db, decision.id, "CLOSED")
        except Exception as e:
          print(f"Error checking pending order {decision.ref_number}: {e}")

  async def check_open_orders(self):
    """Verifica órdenes OPEN y actualiza status si están cerradas"""
    async with DatabaseSession() as db:
      open_orders = await self.decision_repo.get_decision_by_status(db, "OPEN")
      for decision, symbol in open_orders:
        try:
          status = self.binance.get_order_status(symbol, decision.ref_number)
          if status in ["CANCELED", "EXPIRED", "REJECTED", "FILLED"]:
            await self.decision_repo.update_status(db, decision.id, "CLOSED")
        except Exception as e:
          print(f"Error checking open order {decision.ref_number}: {e}")

  async def check_order_expiration(self):
    """Cierra órdenes PLANNED que hayan expirado"""
    async with DatabaseSession() as db:
      planned = await self.decision_repo.get_decision_by_status(db, "PLANNED")
      for decision, symbol in planned:
        expiration_time = decision.created_at + timedelta(minutes=settings.order_expiration_minutes)
        # hay que compararlo convertido a int, porque datetime.now() tiene microsegundos y el expiration_time no
        if int(expiration_time.timestamp()) < int(datetime.now().timestamp()):
          try:
            if decision.ref_number:
              self.binance.cancel_order(symbol, decision.ref_number)
            await self.decision_repo.update_status(db, decision.id, "EXPIRED")
            self.telegram.send_info(self.chat_id, 'check_order_expiration', 'ORDEN CADUCADA', f"Orden PLANNED {decision.id} para {symbol} ha expirado y se ha cerrado.", f"{decision.id}")
            # self.telegram.send_trade_expired(self.chat_id, symbol, decision.side, decision.entry_price, decision.ref_number)
          except Exception as e:
            print(f"Error expiring order {decision.ref_number}: {e}")

  async def check_order_cancelation(self):
      """Cierra órdenes PENDING que hayan superado el tiempo de cancelación"""
      async with DatabaseSession() as db:
        planned = await self.decision_repo.get_decision_by_status(db, "PENDING")
        for decision, symbol in planned:
          cancelation_time = decision.created_at + timedelta(minutes=settings.order_cancelation_minutes)
          # hay que compararlo convertido a int, porque datetime.now() tiene microsegundos y el cancelation_time no
          if int(cancelation_time.timestamp()) < int(datetime.now().timestamp()):
            try:
              if decision.ref_number:
                self.binance.cancel_order(symbol, decision.ref_number)
              await self.decision_repo.update_status(db, decision.id, "CANCELLED")
              self.telegram.send_info(self.chat_id, 'check_order_cancelation', 'ORDEN CANCELADA', f"Orden PENDING {decision.id} para {symbol} ha superado el tiempo de cancelación y se ha cerrado.", f"{decision.id}")
            except Exception as e:
              print(f"Error canceling order {decision.ref_number}: {e}")

  async def run_loop(self):
    last_run = {"15m": None, "1h": None, "4h": None, "1d": None}
    while True:
      await self.check_pending_orders()
      await self.check_open_orders()
      await self.check_order_expiration()
      await self.check_order_cancelation()
      now = datetime.now()
      checks = {
        "15m": (now.minute % 15 == 0, now.minute),
        "1h": (now.minute == 11, now.hour),
        "4h": (now.minute == 0 and now.hour % 4 == 0, now.hour),
        "1d": (now.minute == 0 and now.hour == 0, now.day),
      }
      for interval, (should_run, key) in checks.items():
        if should_run and last_run[interval] != key:
          for symbol in ["BTCUSDT", "ETHUSDT", "BNBUSDT"]:
            try:
              await self.run_cycle(symbol, interval)
            except Exception as e:
              print(f"Error {symbol} {interval}: {e}")
          last_run[interval] = key
      await sleep(30)
