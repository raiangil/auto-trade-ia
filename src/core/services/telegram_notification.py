import requests
from src.config.settings import settings
from datetime import datetime
class TelegramNotificationService:
  bot_name = "BinanceFutureDemoBot"
  _instance_critical = None
  _instance_logs = None

  
  def __init__(self, bot_name: str, bot_token: str):
    self.program_name = bot_name
    self.bot_token = bot_token
    self.base_url = f"https://api.telegram.org"
    self.parse_mode = "HTML"
    self.disable_web_page_preview = True
    self.object_error_code = "003000"
    print(f"TelegramNotificationService initialized with bot_name: {self.program_name}")
  
  @classmethod
  def get_instance(cls):
    if not cls._instance_critical:
      cls._instance_critical = cls("Auto Trade IA", settings.telegram_critical_bot_token)
    if not cls._instance_logs:
      cls._instance_logs = cls("Auto Trade IA", settings.telegram_logging_bot_token)
    return cls._instance_critical, cls._instance_logs

  #region templates
  templates = {
    "critical_error": (
      "🚨 <b>{{program_name}} | ERROR CRITICO</b>\n\n"
      "📌 <b>Evento:</b> {{event}}\n"
      "📍 <b>Location:</b> <code>{{location}}</code>\n\n"
      "⚠️ <b>Error:</b>\n<code>{{compact_error}}</code>\n\n"
      # "🧩 <b>Operation ID:</b> <code>{{operation_id}}</code>\n"
      "🕒 <b>Time:</b> <code>{{now_text}}</code>"
    ),
    "normal_error": (
      "🚨 <b>{{program_name}} | ERROR NORMAL</b>\n\n"
      "📍 <b>Location:</b> <code>{{location}}</code>\n"
      "⚠️ <b>Title:</b> {{title}}\n"
      "🔎 <b>Error:</b> <code>{{error}}</code>\n\n"
      "🕒 <b>Time:</b> <code>{{now_text}}</code>\n"
      "🔁 <b>Key:</b> <code>{{throttle_key}}</code>"
    ),
    "warning": (
      "⚠️ <b>{{program_name}} | ADVERTENCIA</b>\n\n"
      "📍 <b>Location:</b> <code>{{location}}</code>\n"
      "⚠️ <b>Title:</b> {{title}}\n"
      "🔎 <b>Warning:</b> <code>{{warning}}</code>\n\n"
      "🕒 <b>Time:</b> <code>{{now_text}}</code>\n"
    ),
    "info": (
      "✅ <b>{{program_name}} | INFORMACION</b>\n\n"
      "📍 <b>Location:</b> <code>{{location}}</code>\n"
      "ℹ️ <b>Title:</b> {{title}}\n"
      "🔎 <b>Info:</b> <code>{{info}}</code>\n\n"
      "🧩 <b>Operation ID:</b> <code>{{operation_id}}</code>\n"
      "🕒 <b>Time:</b> <code>{{now_text}}</code>\n"
    ),
    "log": (
      "📝 <b>{{program_name}} | LOG</b>\n\n"
      "📍 <b>Location:</b> <code>{{location}}</code>\n"
      "🔎 <b>Info:</b> <code>{{info}}</code>\n\n"
      "🕒 <b>Time:</b> <code>{{now_text}}</code>\n"
    ),
    "order_executed": (
      "💰 <b>{{program_name}} | ORDEN EJECUTADA</b>\n\n"
      "🪙 <b>Symbol:</b> <code>{{symbol}}</code>\n"
      "{{icon}} <b>Side:</b> <code>{{side}}</code>\n"
      "📊 <b>Type:</b> <code>{{order_type}}</code>\n\n"
      "💵 <b>Quantity:</b> <code>{{quantity}}</code>\n"
      "💲 <b>Price:</b> <code>{{price}}</code>\n"
      "💸 <b>Total:</b> <code>{{total}}</code> USDT\n\n"
      "🤖 <b>Bot Name:</b> <code>{{bot_name}}</code>\n"
      "      <b>Type:</b> <code>{{bot_type}}</code>\n"
      "      <b>ID:</b> <code>{{bot_id}}</code>\n\n"
      "🧩 <b>Order ID:</b> <code>{{order_id}}</code>\n"
      "✅ <b>Status:</b> {{status}}\n"
      "🕒 <b>Time:</b> <code>{{now_text}}</code>"
    ),
    "signal_notification": (
      "📈 <b>{{program_name}} | NUEVA SEÑAL</b>\n\n"
      "🪙 <b>Symbol:</b> <code>{{symbol}}</code>\n"
      "{{icon}} <b>Side:</b> <code>{{side}}</code>\n"
      "⚖️ <b>RR:</b> <code>{{rr}}</code> USDT\n\n"

      "⚪ <b>Skip % Prob:</b> <code>{{skip}}</code>\n"
      "🔴 <b>Short % Prob:</b> <code>{{short}}</code>\n"
      "🟢 <b>Long % Prob:</b> <code>{{long}}</code>\n\n"

      "🎯 <b>Entry:</b> <code>{{entry}}</code>\n"
      "🏁 <b>TP:</b> <code>{{tp}}</code>\n"
      "🛑 <b>SL:</b> <code>{{sl}}</code>\n\n"
      
      "🧩 <b>Signal ID:</b> <code>{{id}}</code>\n"
      "⏱ <b>Interval:</b> <code>{{interval}}</code>\n"
      "🕒 <b>Time:</b> <code>{{now_text}}</code>"
    ),
    "trade_opened": (
      "🚀 <b>{{program_name}} | TRADE ABIERTO</b>\n\n"
      "🪙 <b>Symbol:</b> <code>{{symbol}}</code>\n"
      "{{icon}} <b>Side:</b> <code>{{side}}</code>\n\n"
      "🎯 <b>Entry:</b> <code>{{entry}}</code>\n"
      "🏁 <b>TP (2%):</b> <code>{{tp}}</code>\n"
      "🛑 <b>SL (0.67%):</b> <code>{{sl}}</code>\n\n"
      "📊 <b>Opp Prob:</b> <code>{{opp_prob}}</code>\n"
      "📊 <b>Dir Prob:</b> <code>{{dir_prob}}</code>\n\n"
      "🧩 <b>Order ID:</b> <code>{{order_id}}</code>\n"
      "🕒 <b>Time:</b> <code>{{now_text}}</code>"
    ),
    "trade_planned": (
      "🚀 <b>{{program_name}} | TRADE PLANIFICADO</b>\n\n"
      "🪙 <b>Symbol:</b> <code>{{symbol}}</code>\n"
      "{{icon}} <b>Side:</b> <code>{{side}}</code>\n\n"
      "🎯 <b>Entry:</b> <code>{{entry}}</code>\n"
      "🏁 <b>TP (2%):</b> <code>{{tp}}</code>\n"
      "🛑 <b>SL (0.67%):</b> <code>{{sl}}</code>\n\n"
      "📊 <b>Opp Prob:</b> <code>{{opp_prob}}</code>\n"
      "📊 <b>Dir Prob:</b> <code>{{dir_prob}}</code>\n\n"
      "🧩 <b>Order ID:</b> <code>{{order_id}}</code>\n"
      "🕒 <b>Time:</b> <code>{{now_text}}</code>"
    ),
    "trade_rejected": (
      "⚠️ <b>{{program_name}} | TRADE RECHAZADO</b>\n\n"
      "🪙 <b>Symbol:</b> <code>{{symbol}}</code>\n"
      "⏱ <b>Interval:</b> <code>{{interval}}</code>\n\n"
      "✅ <b>Opp Prob:</b> <code>{{opp_prob}}</code> (pasó)\n"
      "❌ <b>Dir Prob:</b> <code>{{dir_prob}}</code> (rechazó)\n"
      "🔎 <b>Side Sugerido:</b> <code>{{side}}</code>\n\n"
      "🕒 <b>Time:</b> <code>{{now_text}}</code>"
    ),
  }
  #endregion
  #region _helper methods
  #endregion
  #region private methods
  def _get_bot_url(self, bot_token: str) -> str:
    return f"{self.base_url}/bot{bot_token}"
  
  def _get_template(self, template_name: str) -> str:
    return self.templates.get(template_name, "")
  
  def _send_message(self, chat_id: str, message: str):
    url = f"{self._get_bot_url(self.bot_token)}/sendMessage"
    data = {
      "chat_id": chat_id,
      "text": message,
      "parse_mode": self.parse_mode,
      "disable_web_page_preview": self.disable_web_page_preview
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
      print("Message sent successfully.")
    else:
      print("Failed to send message. Status code:", response.status_code, response.text)
    return response
  #endregion
  #region public methods
  def send_warning(self, chat_id: str, location: str, title: str, warning: str, now_text: str):
    template = self._get_template("warning")
    message = template.replace("{{program_name}}", self.program_name)\
                      .replace("{{location}}", location)\
                      .replace("{{title}}", title)\
                      .replace("{{warning}}", warning)\
                      .replace("{{now_text}}", now_text)
    self._send_message(chat_id, message)

  def send_info(self, chat_id: str, location: str, title: str, info: str, operation_id: str, now_text: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S'),):
    template = self._get_template("info")
    message = template.replace("{{program_name}}", self.program_name)\
                      .replace("{{location}}", location)\
                      .replace("{{title}}", title)\
                      .replace("{{info}}", info)\
                      .replace("{{operation_id}}", operation_id)\
                      .replace("{{now_text}}", now_text)
    self._send_message(chat_id, message)

  def send_log(self, chat_id: str, location: str, info: str, now_text: str):
    template = self._get_template("log")
    message = template.replace("{{program_name}}", self.program_name)\
                      .replace("{{location}}", location)\
                      .replace("{{info}}", info)\
                      .replace("{{now_text}}", now_text)
    self._send_message(chat_id, message)
  
  def send_normal_error(self, chat_id: str, location: str, title: str, error: str, now_text: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S'), throttle_key: str = None):
    template = self._get_template("normal_error")
    message = template.replace("{{program_name}}", self.program_name)\
                      .replace("{{location}}", location) \
                      .replace("{{title}}", title)\
                      .replace("{{error}}", error)\
                      .replace("{{now_text}}", now_text)\
                      .replace("{{throttle_key}}", throttle_key)
    self._send_message(chat_id, message)
  
  def send_critical_error(self, chat_id: str, location: str, event: str, compact_error: str, now_text: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')):
    template = self._get_template("critical_error")
    message = template.replace("{{program_name}}", self.program_name)\
                      .replace("{{location}}", location)\
                      .replace("{{event}}", event)\
                      .replace("{{compact_error}}", compact_error)\
                      .replace("{{now_text}}", now_text)
    self._send_message(chat_id, message)

  def send_order_executed(self, chat_id: str, symbol: str, side: str, order_type: str, quantity: float, price: float, total: float, order_id: str, status: str, bot_name: str, bot_type: str, bot_id: str, now_text: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')):
    template = self._get_template("order_executed")
    message = template.replace("{{program_name}}", self.program_name)\
                      .replace("{{symbol}}", symbol)\
                      .replace("{{icon}}", "📈" if side.lower() == "buy" else "📉")\
                      .replace("{{side}}", side)\
                      .replace("{{order_type}}", order_type)\
                      .replace("{{quantity}}", str(quantity))\
                      .replace("{{price}}", str(price))\
                      .replace("{{total}}", str(total))\
                      .replace("{{order_id}}", str(order_id))\
                      .replace("{{status}}", status)\
                      .replace("{{now_text}}", now_text)\
                      .replace("{{bot_name}}", bot_name)\
                      .replace("{{bot_type}}", bot_type)\
                      .replace("{{bot_id}}", bot_id)
    self._send_message(chat_id, message)

  def send_signal_notification(self, chat_id: str, symbol: str, side: str, rr: float, skip: float, short: float, long: float, entry: float, tp: float, sl: float, interval: str, id: str):
    now_text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    template = self._get_template("signal_notification")
    message = template.replace("{{program_name}}", self.program_name) \
                      .replace("{{symbol}}", symbol)\
                      .replace("{{icon}}", "📈" if side.lower() == "buy" else "📉")\
                      .replace("{{side}}", side)\
                      .replace("{{rr}}", str(rr))\
                      .replace("{{skip}}", str(skip))\
                      .replace("{{short}}", str(short))\
                      .replace("{{long}}", str(long))\
                      .replace("{{entry}}", str(entry))\
                      .replace("{{tp}}", str(tp))\
                      .replace("{{sl}}", str(sl))\
                      .replace("{{interval}}", interval)\
                      .replace("{{id}}", id)\
                      .replace("{{now_text}}", now_text)
    self._send_message(chat_id, message)

  def send_trade_opened(self, chat_id: str, symbol: str, side: str, entry: float, tp: float, sl: float, opp_prob: float, dir_prob: float, order_id: str):
    now_text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    template = self._get_template("trade_opened")
    message = template.replace("{{program_name}}", self.program_name)\
                      .replace("{{symbol}}", symbol)\
                      .replace("{{icon}}", "📈" if side == "BUY" else "📉")\
                      .replace("{{side}}", side)\
                      .replace("{{entry}}", str(entry))\
                      .replace("{{tp}}", str(tp))\
                      .replace("{{sl}}", str(sl))\
                      .replace("{{opp_prob}}", str(opp_prob))\
                      .replace("{{dir_prob}}", str(dir_prob))\
                      .replace("{{order_id}}", str(order_id))\
                      .replace("{{now_text}}", now_text)
    self._send_message(chat_id, message)

  def send_trade_planned(self, chat_id: str, symbol: str, side: str, entry: float, tp: float, sl: float, opp_prob: float, dir_prob: float, order_id: str):
    now_text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    template = self._get_template("trade_planned")
    message = template.replace("{{program_name}}", self.program_name)\
                      .replace("{{symbol}}", symbol)\
                      .replace("{{icon}}", "📈" if side == "BUY" else "📉")\
                      .replace("{{side}}", side)\
                      .replace("{{entry}}", str(entry))\
                      .replace("{{tp}}", str(tp))\
                      .replace("{{sl}}", str(sl))\
                      .replace("{{opp_prob}}", str(opp_prob))\
                      .replace("{{dir_prob}}", str(dir_prob))\
                      .replace("{{order_id}}", str(order_id))\
                      .replace("{{now_text}}", now_text)
    self._send_message(chat_id, message)

  def send_trade_rejected(self, chat_id: str, symbol: str, interval: str, opp_prob: float, dir_prob: float, side: str):
    now_text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    template = self._get_template("trade_rejected")
    message = template.replace("{{program_name}}", self.program_name)\
                      .replace("{{symbol}}", symbol)\
                      .replace("{{interval}}", interval)\
                      .replace("{{opp_prob}}", str(opp_prob))\
                      .replace("{{dir_prob}}", str(dir_prob))\
                      .replace("{{side}}", side)\
                      .replace("{{now_text}}", now_text)
    self._send_message(chat_id, message)
  #endregion