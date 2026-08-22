from datetime import datetime
from src.core.models import DataSet, Decision
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

class DatasetRepository:
  @staticmethod
  async def create_dataset(db: AsyncSession, dataset: dict):
    ds = DataSet(**dataset)
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    return ds

class DecisionRepository:
  @staticmethod
  async def create_decision(db: AsyncSession, data: dict):
    dec = Decision(**data)
    db.add(dec)
    await db.commit()
    await db.refresh(dec)
    return dec

  @staticmethod
  async def has_active_order(db: AsyncSession, symbol: str) -> bool:
    result = await db.execute(
      select(Decision).join(DataSet).where(
        DataSet.symbol == symbol,
        Decision.status.in_(["PLANNED", "PENDING", "OPEN"]),
        Decision.is_active == True
      )
    )
    return result.first() is not None

  @staticmethod
  async def update_status(db: AsyncSession, decision_id, status: str, ref_number: str = None):
    result = await db.execute(select(Decision).where(Decision.id == decision_id))
    dec = result.scalar_one_or_none()
    if dec:
      dec.status = status
      if ref_number:
        dec.ref_number = ref_number
      dec.updated_at = datetime.utcnow()
      await db.commit()
    return dec

  @staticmethod
  async def get_decision_by_status(db: AsyncSession, status): 
    result = await db.execute(
      select(Decision, DataSet.symbol).join(DataSet).where(
        Decision.status == status,
        Decision.is_active == True
      )
    )
    return result.all()