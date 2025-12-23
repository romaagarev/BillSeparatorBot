import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from aiogram.types import Message, CallbackQuery, User
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from bot.adapters.states import TableStates
from bot.dao.database import Base
from bot.dao.models import User as UserModel, DiningTable, TableUser
from bot.adapters.handlers.table_handler import *

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
    msg.from_user = User(id=1, is_bot=False, first_name="TestUser")
    msg.answer = AsyncMock()
    msg.edit_text = AsyncMock()
    return msg

@pytest_asyncio.fixture
def callback_mock(message_mock):
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = User(id=1, is_bot=False, first_name="TestUser")
    cb.message = message_mock
    cb.data = ""
    cb.answer = AsyncMock()
    return cb

@pytest_asyncio.fixture
async def setup_user_and_table(async_session):
    user = UserModel(telegram_id=1, first_name="User1")
    async_session.add(user)
    await async_session.commit()
    table = DiningTable(name="Table1", invite_code="INV123")
    async_session.add(table)
    await async_session.commit()
    return user, table

@pytest.mark.asyncio
async def test_create_table_start(message_mock, fsm_mock):
    await create_table_start(message_mock, fsm_mock)
    fsm_mock.set_state.assert_awaited_with(TableStates.waiting_for_table_name)
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_create_table_finish_cancel(message_mock, fsm_mock, async_session):
    message_mock.text = "❌ Отмена"
    await create_table_finish(message_mock, fsm_mock, async_session)
    fsm_mock.clear.assert_awaited()
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_create_table_finish_success(message_mock, fsm_mock, async_session, setup_user_and_table):
    user, _ = setup_user_and_table
    message_mock.text = "New Table"
    TableUseCase.create_table = AsyncMock(return_value=(1, "INV999"))
    message_mock.bot.me = AsyncMock(return_value=AsyncMock(username="BotTest"))

    await create_table_finish(message_mock, fsm_mock, async_session)
    fsm_mock.clear.assert_awaited()
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_join_table_start(message_mock, fsm_mock):
    await join_table_start(message_mock, fsm_mock)
    fsm_mock.set_state.assert_awaited_with(TableStates.waiting_for_table_id)
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_join_table_finish_cancel(message_mock, fsm_mock, async_session):
    message_mock.text = "❌ Отмена"
    await join_table_finish(message_mock, fsm_mock, async_session)
    fsm_mock.clear.assert_awaited()
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_join_table_finish_success(message_mock, fsm_mock, async_session, setup_user_and_table):
    user, table = setup_user_and_table
    message_mock.text = "INV123"
    TableUseCase.get_table_by_code = AsyncMock(return_value=table)
    TableUseCase.join_table = AsyncMock()

    await join_table_finish(message_mock, fsm_mock, async_session)
    fsm_mock.clear.assert_awaited()
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_my_tables_no_tables(message_mock, async_session, setup_user_and_table):
    user, _ = setup_user_and_table
    TableUseCase.get_user_tables = AsyncMock(return_value=[])
    await my_tables(message_mock, async_session)
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_my_tables_with_tables(message_mock, async_session, setup_user_and_table):
    user, table = setup_user_and_table
    TableUseCase.get_user_tables = AsyncMock(return_value=[table])
    await my_tables(message_mock, async_session)
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_select_table(callback_mock, fsm_mock):
    callback_mock.data = "table_1"
    await select_table(callback_mock, fsm_mock)
    fsm_mock.update_data.assert_awaited()
    callback_mock.message.edit_text.assert_awaited()
    callback_mock.message.answer.assert_awaited()


@pytest.mark.asyncio
async def test_back_to_tables_no_tables(message_mock, fsm_mock, async_session, setup_user_and_table):
    user, _ = setup_user_and_table
    TableUseCase.get_user_tables = AsyncMock(return_value=[])
    await back_to_tables(message_mock, fsm_mock, async_session)
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_back_to_tables_with_tables(message_mock, fsm_mock, async_session, setup_user_and_table):
    user, table = setup_user_and_table
    TableUseCase.get_user_tables = AsyncMock(return_value=[table])
    await back_to_tables(message_mock, fsm_mock, async_session)
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_main_menu(message_mock, fsm_mock):
    await main_menu(message_mock, fsm_mock)
    fsm_mock.clear.assert_awaited()
    message_mock.answer.assert_awaited()
