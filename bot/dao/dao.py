from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict

from loguru import logger
from sqlalchemy import select, func, case
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.dao.base import BaseDAO
from bot.dao.models import User, DiningTable, Item, TableItem, TableUser, Transaction, UserItemConsumption


class UserDao(BaseDAO[User]):
    model = User

    @classmethod
    async def get_all_user_tables_by_id(cls, session: AsyncSession, user_id: int) -> Optional[Dict[int, str]]:
        try:
            # Запрос для получения общего числа покупок и общей суммы
            result = await session.execute(
                    select(
                        DiningTable.id, DiningTable.name
                    ).join(TableUser).filter(TableUser.user_id == user_id)
                )
            stats = result.one_or_none()

            if stats is None:
                return None

            ids, names = stats
            return {i: name for i, name in zip(ids, names)}

        except SQLAlchemyError as e:
            # Обработка ошибок при работе с базой данных
            print(f"Ошибка при получении всех столов пользователя: {e}")
            return None

    @classmethod
    async def get_total_spent_by_user_and_table_ids(cls, session: AsyncSession, user_id: int, table_id: int) \
            -> int:
        try:
            # Запрос для получения общего числа покупок и общей суммы
            result = await session.execute(
                select(
                    func.sum(UserItemConsumption.ratio * Item.price).label('total_spent')
                ).join(Item).join(TableUser)
                .filter(UserItemConsumption.user_id == user_id, TableUser.table_id == table_id)
            )
            stats = result.one_or_none()

            if stats is None:
                return None

            return stats['total_spent']

        except SQLAlchemyError as e:
            # Обработка ошибок при работе с базой данных
            print(f"Ошибка при получении общей суммы трат пользователя: {e}")
            return None




class DiningTableDao(BaseDAO[DiningTable]):
    model = DiningTable

class ItemDao(BaseDAO[Item]):
    model = Item

class TableItemDao(BaseDAO[TableItem]):
    model = TableItem

class TableUserDao(BaseDAO[TableUser]):
    model = TableUser

class TransactionDao(BaseDAO[Transaction]):
    model = Transaction

class UserDao(BaseDAO[User]):
    model = User

class UserItemConsumptionDao(BaseDAO[UserItemConsumption]):
    model = UserItemConsumption