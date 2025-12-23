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