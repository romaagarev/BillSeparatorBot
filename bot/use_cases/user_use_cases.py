from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.dao.dao import UserDao
from bot.dao.models import User
from pydantic import BaseModel


class CreateUserInput(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    link_to_pay: Optional[str] = None


class UserUseCase:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,

    ) -> User:

        filter_data = CreateUserInput(telegram_id=telegram_id)
        user = await UserDao.find_one_or_none(self.session, filter_data)

        if user:
            return user

        user_data = CreateUserInput(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )

        user = await UserDao.add(self.session, user_data)
        await self.session.commit()
        return user

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        stmt = select(User).filter_by(telegram_id=telegram_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_user_phone(self, telegram_id: int, phone_number: str):
        user = await self.get_user_by_telegram_id(telegram_id)
        if user:
            user.phone_number = phone_number
            await self.session.commit()

    async def update_user_link(self, telegram_id: int, link_to_pay: str):
        user = await self.get_user_by_telegram_id(telegram_id)
        if user:
            user.link_to_pay = link_to_pay
            await self.session.commit()
