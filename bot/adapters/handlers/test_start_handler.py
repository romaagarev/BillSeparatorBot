import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from aiogram.types import Message, User
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from bot.adapters.handlers.start_handler import cmd_start, cmd_help, back_to_main_menu
from bot.dao.database import Base
from bot.dao.models import User as UserModel, DiningTable, TableUser
from bot.use_cases.user_use_cases import UserUseCase

@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session_factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
def fsm_mock():
    state = AsyncMock(spec=FSMContext)
    state.get_data = AsyncMock(return_value={})
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    state.clear = AsyncMock()
    return state


@pytest_asyncio.fixture
def message_mock():
    msg = AsyncMock(spec=Message)
    msg.from_user = User(id=1, is_bot=False, first_name="TestUser", username="testuser")
    msg.answer = AsyncMock()
    msg.text = "/start"
    return msg

@pytest_asyncio.fixture
async def setup_user(async_session):
    user = UserModel(telegram_id=1, first_name="TestUser")
    async_session.add(user)
    await async_session.commit()
    return user


@pytest.mark.asyncio
async def test_cmd_start_without_join(message_mock, fsm_mock, async_session, monkeypatch):
    monkeypatch.setattr(UserUseCase, "get_or_create_user", AsyncMock())

    message_mock.text = "/start"
    await cmd_start(message_mock, async_session, fsm_mock)

    fsm_mock.clear.assert_awaited()
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_cmd_start_with_join_success(message_mock, fsm_mock, async_session, setup_user, monkeypatch):
    table = DiningTable(name="Table1", invite_code="INV123")
    async_session.add(table)
    await async_session.commit()
    monkeypatch.setattr(UserUseCase, "get_or_create_user", AsyncMock())

    from bot.adapters.handlers import start_handler
    table_use_case_mock = AsyncMock()
    table_use_case_mock.get_table_by_code = AsyncMock(return_value=table)
    table_use_case_mock.join_table = AsyncMock()
    monkeypatch.setattr(start_handler, "TableUseCase", lambda session: table_use_case_mock)

    message_mock.text = "/start join_INV123"
    await cmd_start(message_mock, async_session, fsm_mock)

    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_cmd_start_with_join_table_not_found(message_mock, fsm_mock, async_session, monkeypatch):
    monkeypatch.setattr(UserUseCase, "get_or_create_user", AsyncMock())
    from bot.adapters.handlers import start_handler
    table_use_case_mock = AsyncMock()
    table_use_case_mock.get_table_by_code = AsyncMock(return_value=None)
    monkeypatch.setattr(start_handler, "TableUseCase", lambda session: table_use_case_mock)

    message_mock.text = "/start join_INV999"
    await cmd_start(message_mock, async_session, fsm_mock)

    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_cmd_start_with_join_already_member(message_mock, fsm_mock, async_session, setup_user, monkeypatch):
    table = DiningTable(name="Table1", invite_code="INV123")
    async_session.add(table)
    await async_session.commit()
    tu = TableUser(table_id=table.id, user_id=setup_user.id)
    async_session.add(tu)
    await async_session.commit()

    monkeypatch.setattr(UserUseCase, "get_or_create_user", AsyncMock())
    from bot.adapters.handlers import start_handler
    table_use_case_mock = AsyncMock()
    table_use_case_mock.get_table_by_code = AsyncMock(return_value=table)
    monkeypatch.setattr(start_handler, "TableUseCase", lambda session: table_use_case_mock)

    message_mock.text = "/start join_INV123"
    await cmd_start(message_mock, async_session, fsm_mock)

    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_cmd_help(message_mock):
    await cmd_help(message_mock)
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_back_to_main_menu(message_mock, fsm_mock):
    await back_to_main_menu(message_mock, fsm_mock)
    fsm_mock.clear.assert_awaited()
    message_mock.answer.assert_awaited()
