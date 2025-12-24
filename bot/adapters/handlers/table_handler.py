from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.adapters.keyboards import get_main_menu_keyboard, get_cancel_keyboard, get_tables_inline_keyboard, get_table_menu_keyboard
from bot.adapters.states import TableStates
from bot.use_cases.table_use_cases import TableUseCase
from bot.use_cases.user_use_cases import UserUseCase
from pydantic import BaseModel

router = Router()


class UserFilter(BaseModel):
    telegram_id: int


@router.message(F.text == "➕ Создать стол")
async def create_table_start(message: Message, state: FSMContext):
    await state.set_state(TableStates.waiting_for_table_name)
    await message.answer(
        "Введите название стола (например, 'Ужин в ресторане'):",
        reply_markup=get_cancel_keyboard()
    )


@router.message(TableStates.waiting_for_table_name)
async def create_table_finish(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание стола отменено.", reply_markup=get_main_menu_keyboard())
        return
    
    table_name = message.text
    
    from sqlalchemy import select
    from bot.dao.models import User
    
    result = await session.execute(
        select(User).filter_by(telegram_id=message.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await message.answer("Ошибка: пользователь не найден. Используйте /start")
        return
    
    table_use_case = TableUseCase(session)
    table_id, invite_code = await table_use_case.create_table(table_name, user.id)
    
    bot = message.bot
    bot_username = (await bot.me()).username
    invite_link = f"https://t.me/{bot_username}?start=join_{invite_code}"
    
    await state.clear()
    await message.answer(
        f"✅ Стол '{table_name}' создан!\n\n"
        f"🔑 Код приглашения: <code>{invite_code}</code>\n\n"
        f"🔗 Ссылка для присоединения:\n{invite_link}\n\n"
        f"Отправьте код или ссылку друзьям, чтобы они могли присоединиться к столу.",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )


@router.message(F.text == "🔗 Присоединиться к столу")
async def join_table_start(message: Message, state: FSMContext):
    await state.set_state(TableStates.waiting_for_table_id)
    await message.answer(
        "Введите код приглашения стола:",
        reply_markup=get_cancel_keyboard()
    )


@router.message(TableStates.waiting_for_table_id)
async def join_table_finish(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Присоединение отменено.", reply_markup=get_main_menu_keyboard())
        return
    
    invite_code = message.text.strip().upper()
    
    user_use_case = UserUseCase(session)
    from sqlalchemy import select
    from bot.dao.models import User
    
    result = await session.execute(
        select(User).filter_by(telegram_id=message.from_user.id)
    )
    user = result.scalar_one_or_none()

    if not user:
        await message.answer("Ошибка: пользователь не найден. Используйте /start")
        return
    user_id = user.id
    table_use_case = TableUseCase(session)
    
    table = await table_use_case.get_table_by_code(invite_code)
    
    if not table:
        await message.answer(
            "❌ Стол с таким кодом не найден. Проверьте код и попробуйте снова.",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    table_id = table.id
    table_name = table.name
    
    from bot.dao.models import TableUser
    result = await session.execute(
        select(TableUser).filter_by(table_id=table_id, user_id=user_id)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        await state.clear()
        await message.answer(
            "❌ Вы уже являетесь участником этого стола!",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    try:
        await table_use_case.join_table(table_id, user_id)
        await state.clear()
        await message.answer(
            f"✅ Вы успешно присоединились к столу '{table_name}'!",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при присоединении к столу, попробуйте ещё раз",
            reply_markup=get_main_menu_keyboard()
        )


@router.message(F.text == "🍽️ Мои столы")
async def my_tables(message: Message, session: AsyncSession):
    from sqlalchemy import select
    from bot.dao.models import User
    
    result = await session.execute(
        select(User).filter_by(telegram_id=message.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await message.answer("Ошибка: пользователь не найден. Используйте /start")
        return
    
    table_use_case = TableUseCase(session)
    tables = await table_use_case.get_user_tables(user.id)
    
    if not tables:
        await message.answer(
            "У вас пока нет столов.\n"
            "Создайте новый или присоединитесь к существующему!",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    tables_list = [(t.id, t.name) for t in tables]
    await message.answer(
        "Ваши столы:",
        reply_markup=get_tables_inline_keyboard(tables_list)
    )


@router.callback_query(F.data.startswith("table_"))
async def select_table(callback: CallbackQuery, state: FSMContext):
    table_id = int(callback.data.split("_")[1])
    await state.update_data(current_table_id=table_id)
    
    await callback.message.edit_text(
        f"Вы выбрали стол. Используйте меню для работы с ним:",
    )
    await callback.message.answer(
        "Меню стола:",
        reply_markup=get_table_menu_keyboard()
    )


@router.message(F.text == "🔙 Назад к столам")
async def back_to_tables(message: Message, state: FSMContext, session: AsyncSession):
    await state.update_data(current_table_id=None)
    
    from sqlalchemy import select
    from bot.dao.models import User
    
    result = await session.execute(
        select(User).filter_by(telegram_id=message.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await message.answer("Ошибка: пользователь не найден. Используйте /start")
        return
    
    table_use_case = TableUseCase(session)
    tables = await table_use_case.get_user_tables(user.id)
    
    if not tables:
        await message.answer(
            "У вас пока нет столов.\n"
            "Создайте новый или присоединитесь к существующему!",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    tables_list = [(t.id, t.name) for t in tables]
    await message.answer(
        "Ваши столы:",
        reply_markup=get_tables_inline_keyboard(tables_list)
    )


@router.message(F.text == "🚪 Покинуть стол")
async def leave_table(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    current_table_id = data.get("current_table_id")
    
    if not current_table_id:
        await state.clear()
        await message.answer(
            "Сначала выберите стол из списка 'Мои столы'",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    from sqlalchemy import select
    from bot.dao.models import User, DiningTable
    
    result = await session.execute(
        select(User).filter_by(telegram_id=message.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await state.clear()
        await message.answer("Ошибка: пользователь не найден. Используйте /start")
        return
    
    result = await session.execute(
        select(DiningTable).filter(DiningTable.id == current_table_id)
    )
    table = result.scalar_one_or_none()
    
    if not table:
        await state.clear()
        await message.answer("Ошибка: стол не найден.", reply_markup=get_main_menu_keyboard())
        return

    table_name = table.name
    table_use_case = TableUseCase(session)
    success = await table_use_case.leave_table(current_table_id, user.id)
    
    await state.clear()
    
    if success:
        await message.answer(
            f"✅ Вы покинули стол '{table_name}'.\n\n"
            f"Теперь этот стол не будет отображаться в вашем списке.",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await message.answer(
            "❌ Не удалось покинуть стол. Возможно, вы уже не являетесь участником.",
            reply_markup=get_main_menu_keyboard()
        )


@router.message(F.text == "🏠 Главное меню")
async def main_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_menu_keyboard()
    )