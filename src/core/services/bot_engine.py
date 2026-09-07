from asyncio import sleep
from datetime import datetime, timedelta

from src.config.settings import settings

from ..database import DatabaseSession
from .binance_private import BinanceService
from .market_analysis_service import MarketAnalysisService
from .model import ModelService
from .repositories import DatasetRepository, DecisionRepository
from .telegram_notification import TelegramNotificationService


# 3:1 ratio -> 2% TP, 0.67% SL
TP_PCT = 0.02
SL_PCT = 0.0067
MIN_OPP_PROB = 0.58
MIN_DIR_PROB = 0.56


def calculate_entry_price(signal_price: float, side: str, entry_offset_pct: float) -> float:
  """Desplaza signal_price a favor del trade: BUY baja, SELL sube."""
  offset = entry_offset_pct / 100
  if not offset:
    return round(signal_price, 2)
  if side == "BUY":
    return round(signal_price * (1 - offset), 2)
  return round(signal_price * (1 + offset), 2)


class BotEngineService:
  def __init__(self):
    self.market_service = MarketAnalysisService()
    self.dataset_repo = DatasetRepository()
    self.decision_repo = DecisionRepository()
    self.opp_model = ModelService("./models/trade_opportunity_model.pkl")
    self.dir_model = ModelService("./models/trade_direction_model.pkl")
    self.telegram = TelegramNotificationService(
      "Signal IA Bot",
      settings.telegram_signal_bot_token
    )
    self.binance = BinanceService()
    self.chat_id = "8534189049"

  async def run_cycle(self, symbol: str, interval: str):
    async with DatabaseSession() as db:
      # Solo permitimos una oportunidad en espera por símbolo.
      if await self.decision_repo.has_planned_order(db, symbol):
        return

      indicators = self._get_indicators(symbol, interval)

      # Se conserva el delay existente para no alterar el flujo actual.
      await sleep(10)
      dataset = await self.dataset_repo.create_dataset(db, indicators)

      trade = self._evaluate_trade(indicators, symbol, interval)
      if trade is None:
        return

      side, signal_price, entry, tp, sl, opp_prob, dir_prob, offset_pct = trade

      decision = await self.decision_repo.create_decision(db, {
        "dataset_id": dataset.id,
        "status": "PLANNED",
        "side": side,
        "entry_price": entry,
        "signal_price": signal_price,
        "entry_offset_pct": offset_pct,
        "tp_price": tp,
        "sl_price": sl,
        "opportunity_prob": opp_prob,
        "direction_prob": dir_prob,
      })

      # Si existe otra operación del mismo símbolo, esta oportunidad queda
      # PLANNED hasta que la anterior cierre o hasta que expire.
      if await self.decision_repo.has_active_order(db, symbol):
        return

      await self._submit_order(db, decision, symbol)

  def _get_indicators(self, symbol: str, interval: str) -> dict:
    klines_df, _ = self.market_service.get_klines_from_date_df(
      symbol,
      interval,
      None,
      501
    )
    indicators = self.market_service.calculate_symbol_indicators(
      klines_df[:-1]
    )
    indicators["symbol"] = symbol
    indicators["timeframe"] = interval
    return indicators

  def _evaluate_trade(self, indicators: dict, symbol: str, interval: str):
    _, opp_probs = self.opp_model.predict(indicators)
    opp_prob = opp_probs[1]

    if opp_prob < MIN_OPP_PROB:
      return None

    _, dir_probs = self.dir_model.predict(indicators)
    short_prob, long_prob = dir_probs[0], dir_probs[1]

    if short_prob > long_prob:
      side, dir_prob = "SELL", short_prob
    else:
      side, dir_prob = "BUY", long_prob

    if dir_prob < MIN_DIR_PROB:
      self.telegram.send_trade_rejected(
        self.chat_id,
        symbol,
        interval,
        opp_prob,
        dir_prob,
        side
      )
      return None

    current_price = self.market_service.get_current_price_symbol(symbol)
    candle_close = indicators["c_close"]

    if (
      (side == "BUY" and current_price > candle_close)
      or (side == "SELL" and current_price < candle_close)
    ):
      signal_price = candle_close
    else:
      signal_price = current_price

    offset_pct = settings.entry_price_offset_pct
    entry = calculate_entry_price(signal_price, side, offset_pct)

    if side == "BUY":
      tp = round(entry * (1 + TP_PCT), 2)
      sl = round(entry * (1 - SL_PCT), 2)
    else:
      tp = round(entry * (1 - TP_PCT), 2)
      sl = round(entry * (1 + SL_PCT), 2)

    print(
      f"[{symbol}] side={side} signal_price={signal_price} "
      f"entry_offset_pct={offset_pct} entry_price={entry} "
      f"tp_price={tp} sl_price={sl}"
    )

    return side, signal_price, entry, tp, sl, opp_prob, dir_prob, offset_pct

  async def _submit_order(self, db, decision, symbol: str):
    """Envía una decisión PLANNED a Binance cuando el símbolo está libre."""
    try:
      # Segunda protección contra duplicados: si Binance todavía muestra
      # actividad para el símbolo, la decisión se mantiene PLANNED.
      if self.binance.has_active_trade(symbol):
        return

      qty = self.binance.min_amount.get(symbol, 0.001)
      order_id, status = self.binance.open_limit_order(
        symbol,
        decision.side,
        qty,
        decision.entry_price
      )

      await self.decision_repo.update_status(
        db,
        decision.id,
        "PENDING",
        str(order_id)
      )

      if status == "FILLED":
        await self._mark_as_filled(db, decision, symbol, qty)
      elif status == "CANCELED":
        await self.decision_repo.update_status(db, decision.id, "CANCELLED")
      elif status in ("EXPIRED", "REJECTED"):
        final_status = "EXPIRED" if status == "EXPIRED" else "CANCELLED"
        await self.decision_repo.update_status(db, decision.id, final_status)

    except Exception as e:
      print(f"Error abriendo orden {decision.id} para {symbol}: {e}")

  def _get_close_reason(self, decision):
    """
    Determina qué salida cerró la operación.

    Retorna:
      TAKE_PROFIT
      STOP_LOSS
      OTHER
      None -> Binance todavía no refleja un estado final
    """
    tp_status = None
    sl_status = None

    if decision.tp_algo_id:
      tp_order = self.binance.get_algo_order(
        decision.tp_algo_id
      )
      tp_status = tp_order.get("algoStatus")

    if decision.sl_algo_id:
      sl_order = self.binance.get_algo_order(
        decision.sl_algo_id
      )
      sl_status = sl_order.get("algoStatus")

    if tp_status == "FINISHED" and sl_status != "FINISHED":
      return "TAKE_PROFIT"

    if sl_status == "FINISHED" and tp_status != "FINISHED":
      return "STOP_LOSS"

    terminal_statuses = {
      "FINISHED",
      "CANCELED",
      "EXPIRED",
      "REJECTED"
    }

    statuses = [
      status
      for status in (tp_status, sl_status)
      if status is not None
    ]

    # Operaciones viejas que no tienen algoId.
    if not statuses:
      return "OTHER"

    # Si Binance todavía está procesando alguna orden,
    # esperamos al siguiente ciclo.
    if any(
      status not in terminal_statuses
      for status in statuses
    ):
      return None

    return "OTHER"

  async def _mark_as_filled(
    self,
    db,
    decision,
    symbol: str,
    qty: float
  ):
    """Crea TP/SL y guarda la operación como FILLED."""
    tp_algo_id, sl_algo_id = self.binance.set_tp_sl(
      symbol,
      decision.side,
      qty,
      decision.tp_price,
      decision.sl_price
    )

    await self.decision_repo.update_status(
      db,
      decision.id,
      "FILLED",
      tp_algo_id=tp_algo_id,
      sl_algo_id=sl_algo_id
    )

    self.telegram.send_trade_opened(
      self.chat_id,
      symbol,
      decision.side,
      decision.entry_price,
      decision.tp_price,
      decision.sl_price,
      decision.opportunity_prob,
      decision.direction_prob,
      decision.ref_number
    )

  async def check_pending_orders(self):
    """Actualiza las LIMIT pendientes según el estado real de Binance."""
    async with DatabaseSession() as db:
      pending = await self.decision_repo.get_decision_by_status(db, "PENDING")

      for decision, symbol in pending:
        try:
          status = self.binance.get_order_status(
            symbol,
            decision.ref_number
          )

          if status == "FILLED":
            qty = self.binance.min_amount.get(symbol, 0.001)
            await self._mark_as_filled(db, decision, symbol, qty)
          elif status == "CANCELED":
            await self.decision_repo.update_status(
              db,
              decision.id,
              "CANCELLED"
            )
          elif status == "EXPIRED":
            await self.decision_repo.update_status(
              db,
              decision.id,
              "EXPIRED"
            )
          elif status == "REJECTED":
            await self.decision_repo.update_status(
              db,
              decision.id,
              "CANCELLED"
            )
          elif self._tp_reached_before_fill(decision, symbol):
            # El precio ya llegó al TP sin llenar la entrada: ya no aplica.
            self.binance.cancel_order(symbol, decision.ref_number)
            await self.decision_repo.update_status(
              db,
              decision.id,
              "CANCELLED"
            )
            self.telegram.send_info(
              self.chat_id,
              "check_pending_orders",
              "ORDEN INVALIDADA",
              (
                f"Orden PENDING {decision.id} para {symbol} se canceló: "
                "el precio alcanzó el TP antes de llenarse la entrada."
              ),
              f"{decision.id}"
            )

        except Exception as e:
          print(
            f"Error checking pending order "
            f"{decision.ref_number}: {e}"
          )

  async def check_filled_orders(self):
    """Detecta cierre de posiciones FILLED y guarda el motivo."""
    async with DatabaseSession() as db:
      filled = await self.decision_repo.get_decisions_by_statuses(
        db,
        ["FILLED", "OPEN"]
      )

      for decision, symbol in filled:
        try:
          if self.binance.has_open_position(symbol):
            if decision.status == "OPEN":
              await self.decision_repo.update_status(
                db,
                decision.id,
                "FILLED"
              )

            continue

          close_reason = self._get_close_reason(decision)

          # Puede existir un pequeño delay entre el cierre de la
          # posición y la actualización del Algo Order en Binance.
          if close_reason is None:
            continue

          await self.decision_repo.update_status(
            db,
            decision.id,
            "CLOSED",
            close_reason=close_reason
          )

        except Exception as e:
          print(
            f"Error checking filled order "
            f"{decision.id}: {e}"
          )

  async def check_planned_orders(self):
    """Expira PLANNED vencidas o las envía cuando el símbolo queda libre."""
    async with DatabaseSession() as db:
      planned = await self.decision_repo.get_decision_by_status(
        db,
        "PLANNED"
      )

      for decision, symbol in planned:
        if self._is_expired(
          decision.created_at,
          settings.order_expiration_minutes
        ):
          await self.decision_repo.update_status(
            db,
            decision.id,
            "EXPIRED"
          )
          self.telegram.send_info(
            self.chat_id,
            "check_planned_orders",
            "ORDEN CADUCADA",
            f"Orden PLANNED {decision.id} para {symbol} ha expirado.",
            f"{decision.id}"
          )
          continue

        if await self.decision_repo.has_active_order(db, symbol):
          continue

        # Recalcular entry/TP/SL con precio actual antes de enviar.
        # signal_price y entry_offset_pct NO se tocan: quedan fijos desde
        # la creación de la señal. Fallback a settings solo para registros
        # históricos donde entry_offset_pct sea NULL.
        offset_pct = (
          decision.entry_offset_pct
          if decision.entry_offset_pct is not None
          else settings.entry_price_offset_pct
        )
        current_price = self.market_service.get_current_price_symbol(symbol)
        candidate_entry = calculate_entry_price(
          current_price, decision.side, offset_pct
        )

        # BUY: usar el precio más bajo (mejor entrada)
        # SELL: usar el precio más alto (mejor entrada)
        if decision.side == "BUY":
          entry = min(candidate_entry, decision.entry_price)
        else:
          entry = max(candidate_entry, decision.entry_price)

        # Recalcular TP/SL basado en el nuevo entry
        if decision.side == "BUY":
          tp = round(entry * (1 + TP_PCT), 2)
          sl = round(entry * (1 - SL_PCT), 2)
        else:
          tp = round(entry * (1 - TP_PCT), 2)
          sl = round(entry * (1 + SL_PCT), 2)
        
        # Actualizar precios en la decisión
        await self.decision_repo.update_prices(
          db, decision.id, entry, tp, sl
        )
        decision.entry_price = entry
        decision.tp_price = tp
        decision.sl_price = sl

        await self._submit_order(db, decision, symbol)

  async def check_order_cancelation(self):
    """Cancela PENDING que superaron el tiempo configurado."""
    async with DatabaseSession() as db:
      pending = await self.decision_repo.get_decision_by_status(
        db,
        "PENDING"
      )

      for decision, symbol in pending:
        # updated_at representa cuándo la PLANNED pasó a PENDING.
        pending_since = decision.updated_at or decision.created_at

        if not self._is_expired(
          pending_since,
          settings.order_cancelation_minutes
        ):
          continue

        try:
          if decision.ref_number:
            self.binance.cancel_order(symbol, decision.ref_number)

          await self.decision_repo.update_status(
            db,
            decision.id,
            "CANCELLED"
          )

          self.telegram.send_info(
            self.chat_id,
            "check_order_cancelation",
            "ORDEN CANCELADA",
            (
              f"Orden PENDING {decision.id} para {symbol} ha superado "
              "el tiempo de cancelación."
            ),
            f"{decision.id}"
          )

        except Exception as e:
          print(f"Error canceling order {decision.ref_number}: {e}")

  @staticmethod
  def _is_expired(started_at: datetime, minutes: int) -> bool:
    expiration_time = started_at + timedelta(minutes=minutes)
    now = (
      datetime.now(started_at.tzinfo)
      if started_at.tzinfo
      else datetime.now()
    )
    return now >= expiration_time

  def _tp_reached_before_fill(self, decision, symbol: str) -> bool:
    """True si el mercado ya tocó el TP sin que la entrada se haya llenado."""
    current_price = self.market_service.get_current_price_symbol(symbol)
    if decision.side == "BUY":
      return current_price >= decision.tp_price
    return current_price <= decision.tp_price

  async def run_loop(self):
    last_run = {
      "15m": None,
      "1h": None,
      "4h": None,
      "1d": None
    }

    while True:
      await self.check_pending_orders()
      await self.check_filled_orders()
      await self.check_order_cancelation()
      await self.check_planned_orders()

      now = datetime.now()
      checks = {
        "15m": (now.minute % 15 == 0, now.minute),
        "1h": (now.minute == 11, now.hour),
        "4h": (now.minute == 0 and now.hour % 4 == 0, now.hour),
        "1d": (now.minute == 0 and now.hour == 0, now.day),
      }

      for interval, (should_run, key) in checks.items():
        if not should_run or last_run[interval] == key:
          continue

        for symbol in ["BTCUSDT", "ETHUSDT", "BNBUSDT"]:
          try:
            await self.run_cycle(symbol, interval)
          except Exception as e:
            print(f"Error {symbol} {interval}: {e}")

        last_run[interval] = key

      await sleep(30)
