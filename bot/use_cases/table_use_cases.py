from typing import Optional, List
import secrets
import string
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.dao.dao import DiningTableDao, TableUserDao, UserDao
from bot.dao.models import DiningTable, TableUser, User
from bot.domain.entities import TableEntity, UserEntity
from pydantic import BaseModel


class CreateTableInput(BaseModel):
    name: str
    invite_code: str


class JoinTableInput(BaseModel):
    table_id: int
    user_id: int


class TableUseCase:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _generate_invite_code(self, length: int = 8) -> str:
        characters = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(characters) for _ in range(length))

    async def _is_invite_code_unique(self, invite_code: str) -> bool:
        result = await self.session.execute(
            select(DiningTable).filter(DiningTable.invite_code == invite_code)
        )
        return len(result.scalars().all()) == 0

    async def create_table(self, name: str, creator_id: int) -> tuple[int, str]:
        invite_code = self._generate_invite_code()
        while not await self._is_invite_code_unique(invite_code):
            invite_code = self._generate_invite_code()
        
        table_data = CreateTableInput(name=name, invite_code=invite_code)
        table = await DiningTableDao.add(self.session, table_data)
        table_id = table.id
        
        join_data = JoinTableInput(table_id=table_id, user_id=creator_id)
        await TableUserDao.add(self.session, join_data)
        
        await self.session.commit()
        return table_id, invite_code

    async def join_table(self, table_id: int, user_id: int) -> bool:
        join_data = JoinTableInput(table_id=table_id, user_id=user_id)
        await TableUserDao.add(self.session, join_data)
        await self.session.commit()
        return True

    async def join_table_by_code(self, invite_code: str, user_id: int) -> Optional[int]:
        result = await self.session.execute(
            select(DiningTable).filter(DiningTable.invite_code == invite_code)
        )
        table = result.scalar_one_or_none()
        
        if not table:
            return None
        
        join_data = JoinTableInput(table_id=table.id, user_id=user_id)
        await TableUserDao.add(self.session, join_data)
        await self.session.commit()
        return table.id

    async def get_table_by_code(self, invite_code: str) -> Optional[DiningTable]:
        result = await self.session.execute(
            select(DiningTable).filter(DiningTable.invite_code == invite_code)
        )
        return result.scalar_one_or_none()

    async def get_user_tables(self, user_id: int) -> List[TableEntity]:
        from sqlalchemy import select
        from bot.dao.models import TableUser, DiningTable
        
        result = await self.session.execute(
            select(DiningTable)
            .join(TableUser, TableUser.table_id == DiningTable.id)
            .filter(TableUser.user_id == user_id)
        )
        tables = result.scalars().all()
        return [TableEntity(name=table.name, id=table.id) for table in tables]

    async def leave_table(self, table_id: int, user_id: int) -> bool:
        from sqlalchemy import delete
        
        result = await self.session.execute(
            delete(TableUser).filter(
                TableUser.table_id == table_id,
                TableUser.user_id == user_id
            )
        )
        await self.session.commit()
        return result.rowcount > 0