from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from bot.dao.dao import UserDao
from bot.domain.entities import UserEntity
from pydantic import BaseModel


class CreateUserInput(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserUseCase:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_user(self, telegram_id: int, username: Optional[str] = None,
                                  first_name: Optional[str] = None, last_name: Optional[str] = None) -> int:
        filter_data = CreateUserInput(telegram_id=telegram_id)
        user = await UserDao.find_one_or_none(self.session, filter_data)
        
        if user:
            return user.id
        
        user_data = CreateUserInput(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        user = await UserDao.add(self.session, user_data)
        user_id = user.id
        await self.session.commit()
        return user_id
