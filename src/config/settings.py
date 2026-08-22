"""
Configuración centralizada de la aplicación.
Usa pydantic-settings para validación y manejo de variables de entorno.
"""
import os
from pydantic import Field
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent.parent

def _env_bool(name: str, default: bool = False) -> bool:
  value = os.getenv(name)
  if value is None:
    return default
  return str(value).strip().lower() in {"1", "true", "t", "yes", "y", "on"}


class Settings(BaseSettings):
  """Configuración de la aplicación"""
  
  # Información básica de la API
  app_name: str = "Trading API"
  version: str = "1.0.0"
  debug: bool = False
  
  # CORS (para frontend)
  allowed_origins: list[str] = Field(
    default=["http://localhost:5173", "http://localhost:3000", "http://192.168.100.221:5173"]
  )
  
  # Base de datos
  database_url: str = Field(
    description="PostgreSQL connection string"
  )
  # database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://raian:123456@aquiles:5432/signal_bot_db")
  indicator_lookback_limit: int = Field(
    default=500,
    description="Number of past candles to consider for indicator calculations"
  )
  indicator_future_limit: int = Field(
    default=100,
    description="Number of future candles to consider for indicator calculations"
  )
  max_minutes_to_target: int = Field(
    default=720,
    description="Maximum number of minutes to reach the target"
  )
  target_take_profit_pct: float = Field(
    default=2.0,
    description="Target move percentage"
  )
  target_stop_loss_pct: float = Field(
    default=0.64,
    description="Target stop loss percentage"
  )
  telegram_signal_bot_token: str = Field(
    default="8956497896:AAF8rE-6Q94K6kvPzO9Lg2LAS4w5GUVmeVA",
    description="Telegram signal bot token"
  )
  max_operations_per_day: int = Field(
    default=5,
    description="Maximum number of operations allowed per day"
  )
  pocket_api_key: str = Field(
    description="Pocket API key"
  )
  pocket_api_secret: str = Field(
    description="Pocket API secret"
  )
  binance_api_key: str = Field(
    default="",
    description="Binance API key"
  )
  binance_api_secret: str = Field(
    default="",
    description="Binance API secret"
  )
  order_expiration_minutes: int = Field(
    description="Number of minutes after which a PLANNED order expires"
  )
  order_cancelation_minutes: int = Field(
    description="Number of minutes after which a OPEN order is canceled"
  )
  print(BASE_DIR)
  model_config = SettingsConfigDict(
    env_file=str(BASE_DIR / ".env"),
    env_file_encoding="utf-8",
    case_sensitive=False,
    extra="ignore"  # Ignora variables extra del .env
  )


# Instancia única de configuración
settings = Settings()
