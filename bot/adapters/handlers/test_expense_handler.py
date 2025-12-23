import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from aiogram.types import Message, CallbackQuery, User
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from bot.adapters.states import ExpenseStates
from bot.dao.database import Base
from bot.dao.models import User as UserModel, DiningTable, TableUser, Item, TableItem, UserItemConsumption
from bot.use_cases.expense_use_cases import ExpenseUseCase
from bot.adapters.handlers.expense_handler import *

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
    msg.edit_reply_markup = AsyncMock()
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
async def setup_table(async_session):
    users = []
    for i in range(1, 4):
        u = UserModel(telegram_id=i, first_name=f"User{i}")
        async_session.add(u)
        users.append(u)
    await async_session.commit()

    table = DiningTable(name="Table1", invite_code="INV123")
    async_session.add(table)
    await async_session.commit()

    for u in users:
        link = TableUser(table_id=table.id, user_id=u.id)
        async_session.add(link)
    await async_session.commit()
    return users, table

@pytest.mark.asyncio
async def test_add_expense_start_no_table(message_mock, fsm_mock):
    fsm_mock.get_data.return_value = {}
    await add_expense_start(message_mock, fsm_mock)
    message_mock.answer.assert_awaited()
    assert "Сначала выберите стол" in message_mock.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_add_expense_start_with_table(message_mock, fsm_mock, setup_table):
    _, table = setup_table
    fsm_mock.get_data.return_value = {"current_table_id": table.id}
    await add_expense_start(message_mock, fsm_mock)
    fsm_mock.set_state.assert_awaited_with(ExpenseStates.choosing_type)
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_transaction_type_selected_income(callback_mock, fsm_mock):
    callback_mock.data = "income"
    callback_mock.message.edit_text = AsyncMock()
    callback_mock.message.answer = AsyncMock()
    await transaction_type_selected(callback_mock, fsm_mock)
    fsm_mock.update_data.assert_awaited()
    fsm_mock.set_state.assert_awaited()
    callback_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_add_expense_name_cancel(message_mock, fsm_mock):
    message_mock.text = "❌ Отмена"
    await add_expense_name(message_mock, fsm_mock)
    fsm_mock.clear.assert_awaited()
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_add_expense_price_cancel(message_mock, fsm_mock, async_session):
    message_mock.text = "❌ Отмена"
    await add_expense_price(message_mock, fsm_mock, async_session)
    fsm_mock.clear.assert_awaited()
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_add_expense_price_invalid(message_mock, fsm_mock, async_session):
    message_mock.text = "abc"
    await add_expense_price(message_mock, fsm_mock, async_session)
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_split_all_selected(async_session, callback_mock, fsm_mock, setup_table):
    users, table = setup_table
    fsm_mock.get_data.return_value = {
        "item_name": "Pizza",
        "price": 1000,
        "current_table_id": table.id,
        "is_income": False,
        "table_users": [(u.id, u.first_name) for u in users]
    }
    callback_mock.data = "split_all"
    callback_mock.message.edit_text = AsyncMock()
    callback_mock.message.answer = AsyncMock()
    await split_all_selected(callback_mock, fsm_mock, async_session)
    callback_mock.message.edit_text.assert_awaited()
    callback_mock.message.answer.assert_awaited()


@pytest.mark.asyncio
async def test_split_me_selected(async_session, callback_mock, fsm_mock, setup_table):
    users, table = setup_table
    fsm_mock.get_data.return_value = {
        "item_name": "Pizza",
        "price": 1000,
        "current_table_id": table.id,
        "is_income": False
    }
    callback_mock.data = "split_me"
    callback_mock.message.edit_text = AsyncMock()
    callback_mock.message.answer = AsyncMock()
    await split_me_selected(callback_mock, fsm_mock, async_session)
    callback_mock.message.edit_text.assert_awaited()


@pytest.mark.asyncio
async def test_split_custom_selected(callback_mock, fsm_mock, setup_table):
    users, table = setup_table
    fsm_mock.get_data.return_value = {
        "table_users": [(u.id, u.first_name) for u in users]
    }
    callback_mock.data = "split_custom"
    callback_mock.message.edit_text = AsyncMock()
    await split_custom_selected(callback_mock, fsm_mock)
    fsm_mock.update_data.assert_awaited()
    fsm_mock.set_state.assert_awaited()
    callback_mock.message.edit_text.assert_awaited()


@pytest.mark.asyncio
async def test_toggle_participant(callback_mock, fsm_mock, setup_table):
    users, table = setup_table
    fsm_mock.get_data.return_value = {
        "selected_participants": [users[0].id],
        "table_users": [(u.id, u.first_name) for u in users]
    }
    callback_mock.data = f"participant_{users[1].id}"
    callback_mock.message.edit_reply_markup = AsyncMock()
    await toggle_participant(callback_mock, fsm_mock)
    fsm_mock.update_data.assert_awaited()
    callback_mock.message.edit_reply_markup.assert_awaited()


@pytest.mark.asyncio
async def test_participants_done_no_selection(callback_mock, fsm_mock, setup_table):
    _, table = setup_table
    fsm_mock.get_data.return_value = {
        "selected_participants": [],
        "table_users": []
    }
    callback_mock.answer = AsyncMock()
    await participants_done(callback_mock, fsm_mock)
    callback_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_ratios_entered_equal(async_session, message_mock, fsm_mock, setup_table):
    users, table = setup_table
    fsm_mock.get_data.return_value = {
        "selected_participants": [u.id for u in users],
        "item_name": "Pizza",
        "price": 1200,
        "current_table_id": table.id,
        "is_income": False
    }
    message_mock.text = "поровну"
    await ratios_entered(message_mock, fsm_mock, async_session)
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_ratios_entered_custom(async_session, message_mock, fsm_mock, setup_table):
    users, table = setup_table
    fsm_mock.get_data.return_value = {
        "selected_participants": [u.id for u in users],
        "item_name": "Pizza",
        "price": 1200,
        "current_table_id": table.id,
        "is_income": False
    }
    message_mock.text = "1 2 1"
    await ratios_entered(message_mock, fsm_mock, async_session)
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_view_balance(async_session, message_mock, fsm_mock, setup_table):
    users, table = setup_table
    fsm_mock.get_data.return_value = {"current_table_id": table.id}
    await view_balance(message_mock, fsm_mock, async_session)
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_view_participants(async_session, message_mock, fsm_mock, setup_table):
    users, table = setup_table
    fsm_mock.get_data.return_value = {"current_table_id": table.id}
    await view_participants(message_mock, fsm_mock, async_session)
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_view_statistics(async_session, message_mock, fsm_mock, setup_table):
    users, table = setup_table
    fsm_mock.get_data.return_value = {"current_table_id": table.id}
    await view_statistics(message_mock, fsm_mock, async_session)
    message_mock.answer.assert_awaited()


@pytest.mark.asyncio
async def test_view_operations_history_empty(async_session, message_mock, fsm_mock, setup_table):
    users, table = setup_table
    fsm_mock.get_data.return_value = {"current_table_id": table.id}
    await view_operations_history(message_mock, fsm_mock, async_session)
    message_mock.answer.assert_awaited()
