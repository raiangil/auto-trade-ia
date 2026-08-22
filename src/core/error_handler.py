from src.core.services.telegram_notification import TelegramNotificationService
from src.config.settings import settings
from datetime import datetime

class BaseException(Exception):
  def __init__(self, message="Base Error"):
    self.message = message
    super().__init__(self.message)

class SatcryptException(BaseException):
  def __init__(self, message="Decrypt Error"):
    self.message = message
    super().__init__(self.message)

class UserRepositoryException(BaseException):
  def __init__(self, message="User Repository Error"):
    self.message = message
    super().__init__(self.message)

class PocketRepositoryException(BaseException):
  def __init__(self, message="Pocket Repository Error"):
    self.message = message
    super().__init__(self.message)

class BotRepositoryException(BaseException):
  def __init__(self, message="Bot Repository Error"):
    self.message = message
    super().__init__(self.message)

class BotChildRepositoryException(BaseException):
  def __init__(self, message="Bot Child Repository Error"):
    self.message = message
    super().__init__(self.message)

class BotServiceException(BaseException):
  def __init__(self, message="Bot Service Error"):
    self.message = message
    super().__init__(self.message)

class WebSocketServiceException(BaseException):
  def __init__(self, message="WebSocket Service Error"):
    self.message = message
    super().__init__(self.message)

class TelegramNotificationServiceException(BaseException):
  def __init__(self, message="Telegram Notification Service Error"):
    self.message = message
    super().__init__(self.message)

class SpotMarketMonitorServiceException(BaseException):
  def __init__(self, message="Spot Market Monitor Service Error"):
    self.message = message
    super().__init__(self.message)

class BinancePrivateServiceException(BaseException):
  def __init__(self, message="Binance Private Service Error"):
    self.message = message
    super().__init__(self.message)


class ExceptionHandler():
  warning_counts = {}
  notification_service_critical, notification_service_log = TelegramNotificationService.get_instance()
  bot_name = "Auto Trade IA"
  
  @classmethod
  def handle_warning(cls, warning: str, desc: str, location: str):
    cls.warning_counts[warning.split("|")[0]] = cls.warning_counts.get(warning.split("|")[0], 0) + 1
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if cls.warning_counts[warning.split('|')[0]] % settings.warning_notification_interval == 0:
      cls.notification_service_critical.send_warning(settings.telegram_critical_chat_id, location, warning, desc, now_text)

    cls.notification_service_log.send_warning(settings.telegram_logging_chat_id, location, warning, desc, now_text)

  @classmethod
  def handle_error(cls, error: str, desc: str, location: str, event: str):
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cls.notification_service_critical.send_critical_error(settings.telegram_critical_chat_id, location, event, desc, now_text)
    cls.notification_service_log.send_critical_error(settings.telegram_logging_chat_id, location, event, desc, now_text)
