"""
Configuración de la base de datos.
Este archivo maneja la conexión con PostgreSQL usando SQLAlchemy async.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import Boolean, String, DateTime, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
from uuid import UUID

from ..config.settings import settings


# Motor de base de datos (Async)
# echo=True muestra los queries SQL en consola (útil para debug)
engine = create_async_engine(
  settings.database_url,
  echo=settings.debug,
  future=True,
  # Configuración del pool de conexiones
  pool_size=20,              # Número de conexiones permanentes
  max_overflow=10,           # Conexiones adicionales permitidas
  pool_timeout=30,           # Timeout para obtener conexión del pool
  pool_recycle=3600,         # Reciclar conexiones cada hora
  pool_pre_ping=True,        # Verificar que la conexión esté viva antes de usarla
)

# Fábrica de sesiones
# Una sesión es como una "conversación" con la DB
# expire_on_commit=False evita que los objetos se invaliden después de commit
AsyncSessionLocal = async_sessionmaker(
  engine,
  class_=AsyncSession,
  expire_on_commit=False,
)


# Base para los modelos
# Todos los modelos heredan de esta clase
class ViewBase(DeclarativeBase):
  pass
class Base(DeclarativeBase):
  """
  Columnas que coinciden exactamente con tu tabla
  """
  # Columnas que coinciden exactamente con tu tabla
  id: Mapped[UUID] = mapped_column(
    primary_key=True,
    server_default=text("gen_random_uuid()")
  )
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    nullable=False,
    server_default=text("now()")
  )
  updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    nullable=False,
    server_default=text("now()")
  )
  created_by: Mapped[str] = mapped_column(
    String,
    nullable=False,
    server_default=text("'NOT DEFINED'")
  )
  updated_by: Mapped[str] = mapped_column(
    String,
    nullable=False,
    server_default=text("'NOT DEFINED'")
  )
  is_active: Mapped[bool] = mapped_column(
    Boolean,
    nullable=False,
    server_default=text("true")
  )

async def get_db() -> AsyncSession:
  """
  Dependency para obtener una sesión de base de datos.
  FastAPI se encarga de cerrarla automáticamente cuando termina la petición.
  
  Uso en endpoints:
    @router.get("/users")
    async def get_users(db: AsyncSession = Depends(get_db)):
      # Usar db aquí
  """
  async with AsyncSessionLocal() as session:
    try:
      yield session
    finally:
      await session.close()

async def get_session() -> AsyncSession:
  """
  Obtiene una sesión de base de datos para usar fuera de FastAPI.
  IMPORTANTE: Debes cerrar la sesión manualmente con await session.close()
  
  Uso en servicios/scripts:
    session = await get_session()
    try:
      # Usar session aquí
      result = await session.execute(select(User))
    finally:
      await session.close()
  """
  return AsyncSessionLocal()


class DatabaseSession:
  """
  Context manager para manejar sesiones de base de datos de forma segura.
  Cierra automáticamente la sesión al salir del bloque.
  
  Uso recomendado (con context manager):
    async with DatabaseSession() as db:
      result = await db.execute(select(User))
      users = result.scalars().all()
  """
  
  def __init__(self):
    self.session: AsyncSession = None
  
  async def __aenter__(self) -> AsyncSession:
    """Entra al context manager y crea la sesión"""
    self.session = AsyncSessionLocal()
    return self.session
  
  async def __aexit__(self, exc_type, exc_val, exc_tb):
    """Sale del context manager y cierra la sesión"""
    if self.session:
      await self.session.close()
