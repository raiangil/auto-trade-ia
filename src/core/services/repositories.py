from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import DataSet, Decision


class DatasetRepository:
  @staticmethod
  async def create_dataset(db: AsyncSession, dataset: dict):
    ds = DataSet(**dataset)
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    return ds


class DecisionRepository:
  ACTIVE_STATUSES = ("PENDING", "FILLED", "OPEN")

  @staticmethod
  async def create_decision(db: AsyncSession, data: dict):
    dec = Decision(**data)
    db.add(dec)
    await db.commit()
    await db.refresh(dec)
    return dec

  @classmethod
  async def has_active_order(cls, db: AsyncSession, symbol: str) -> bool:
    """Indica si el símbolo tiene una orden enviada o una posición abierta."""
    result = await db.execute(
      select(Decision.id)
      .join(DataSet)
      .where(
        DataSet.symbol == symbol,
        Decision.status.in_(cls.ACTIVE_STATUSES),
        Decision.is_active.is_(True)
      )
      .limit(1)
    )
    return result.scalar_one_or_none() is not None

  @staticmethod
  async def has_planned_order(db: AsyncSession, symbol: str) -> bool:
    """Evita acumular más de una oportunidad PLANNED por símbolo."""
    result = await db.execute(
      select(Decision.id)
      .join(DataSet)
      .where(
        DataSet.symbol == symbol,
        Decision.status == "PLANNED",
        Decision.is_active.is_(True)
      )
      .limit(1)
    )
    return result.scalar_one_or_none() is not None

  @staticmethod
  async def update_status(
    db: AsyncSession,
    decision_id,
    status: str,
    ref_number: str | None = None,
    tp_algo_id: int | None = None,
    sl_algo_id: int | None = None,
    close_reason: str | None = None
  ):
    result = await db.execute(
      select(Decision).where(
        Decision.id == decision_id
      )
    )

    decision = result.scalar_one_or_none()

    if decision is None:
      return None

    decision.status = status

    if ref_number is not None:
      decision.ref_number = ref_number

    if tp_algo_id is not None:
      decision.tp_algo_id = tp_algo_id

    if sl_algo_id is not None:
      decision.sl_algo_id = sl_algo_id

    if close_reason is not None:
      decision.close_reason = close_reason

    decision.updated_at = datetime.now()

    await db.commit()

    return decision

  @staticmethod
  async def update_prices(
    db: AsyncSession,
    decision_id,
    entry_price: float,
    tp_price: float,
    sl_price: float
  ):
    result = await db.execute(
      select(Decision).where(Decision.id == decision_id)
    )
    decision = result.scalar_one_or_none()
    if decision is None:
      return None
    
    decision.entry_price = entry_price
    decision.tp_price = tp_price
    decision.sl_price = sl_price
    decision.updated_at = datetime.now()
    await db.commit()
    return decision

  @classmethod
  async def get_decision_by_status(cls, db: AsyncSession, status: str):
    return await cls.get_decisions_by_statuses(db, [status])

  @staticmethod
  async def get_decisions_by_statuses(db: AsyncSession, statuses: list[str]):
    result = await db.execute(
      select(Decision, DataSet.symbol)
      .join(DataSet)
      .where(
        Decision.status.in_(statuses),
        Decision.is_active.is_(True)
      )
      .order_by(Decision.created_at.asc())
    )
    return result.all()
