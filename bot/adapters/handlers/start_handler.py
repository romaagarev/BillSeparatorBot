from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.adapters.keyboards import get_main_menu_keyboard, get_yes_no_keyboard
from bot.use_cases.user_use_cases import UserUseCase
from bot.use_cases.table_use_cases import TableUseCase
from bot.adapters.states import RegistrationState
from bot.dao.models import User, TableUser


router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()

    user_use_case = UserUseCase(session)

    await user_use_case.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )

    stmt = select(User).filter_by(telegram_id=message.from_user.id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    command_args = message.text.split(maxsplit=1)
    invite_code = None
    if len(command_args) > 1 and command_args[1].startswith("join_"):
        invite_code = command_args[1][5:]

    if not user.phone_number or not user.link_to_pay:
        if invite_code:
            await state.update_data(pending_invite_code=invite_code)

        tg_phone = getattr(message.from_user, "phone_number", None)

        if tg_phone:
            await state.update_data(tg_phone=tg_phone)

            await state.set_state(RegistrationState.confirm_phone)
            await message.answer(
                f"📱 Я нашёл твой номер в Telegram:\n\n"
                f"<b>{tg_phone}</b>\n\n"
                f"Подходит ли он для переводов?",
                reply_markup=get_yes_no_keyboard(),
                parse_mode="HTML"
            )
        else:
            await state.set_state(RegistrationState.enter_phone)
            await message.answer(
                "📱 Введи, пожалуйста, номер телефона для переводов\n\n"
                "В формате: +79998887766"
            )

        return

    if invite_code:
        table_use_case = TableUseCase(session)
        table = await table_use_case.get_table_by_code(invite_code)

        if not table:
            await message.answer(
                "❌ Стол с таким кодом не найден.\n\n"
                "Возможно, ссылка устарела или код введен неверно.",
                reply_markup=get_main_menu_keyboard()
            )
            return

        result = await session.execute(
            select(TableUser).filter_by(table_id=table.id, user_id=user.id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            await message.answer(
                f"ℹ️ Вы уже являетесь участником стола '{table.name}'!",
                reply_markup=get_main_menu_keyboard()
            )
            return

        try:
            await table_use_case.join_table(table.id, user.id)
            await message.answer(
                f"✅ Вы успешно присоединились к столу '{table.name}'!\n\n"
                f"Теперь вы можете добавлять расходы и просматривать баланс.",
                reply_markup=get_main_menu_keyboard()
            )
        except Exception as e:
            await message.answer(
                f"❌ Ошибка при присоединении к столу: {str(e)}",
                reply_markup=get_main_menu_keyboard()
            )
        return

    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Я бот для разделения счетов...",
        reply_markup=get_main_menu_keyboard()
    )

@router.message(RegistrationState.confirm_phone)
async def confirm_phone(message: Message, state: FSMContext, session: AsyncSession):
    user_data = await state.get_data()
    tg_phone = user_data.get("tg_phone")

    if message.text == "Да":
        phone = tg_phone
    else:
        await state.set_state(RegistrationState.enter_phone)
        await message.answer("Введите номер телефона в формате +79998887766")
        return

    user_use_case = UserUseCase(session)
    await user_use_case.update_user_phone(
        telegram_id=message.from_user.id,
        phone_number=phone
    )

    await state.set_state(RegistrationState.enter_bank)
    await message.answer("🏦 Укажите ваш приоритетный банк (например: Сбер, Т-Банк):")


@router.message(RegistrationState.enter_phone)
async def enter_phone(message: Message, state: FSMContext, session: AsyncSession):

    phone = message.text.strip()

    if not phone.startswith("+") or len(phone) < 10:
        await message.answer("❌ Номер некорректен. Попробуйте ещё раз.\nНапример: +79998887766")
        return

    user_use_case = UserUseCase(session)
    await user_use_case.update_user_phone(
        telegram_id=message.from_user.id,
        phone_number=phone
    )

    await state.set_state(RegistrationState.enter_bank)
    await message.answer("🏦 Укажите ваш приоритетный банк (например: Сбер, Т-Банк):")


@router.message(RegistrationState.enter_bank)
async def enter_bank(message: Message, state: FSMContext, session: AsyncSession):

    bank = message.text.strip()

    user_use_case = UserUseCase(session)
    await user_use_case.update_user_link(
        telegram_id=message.from_user.id,
        link_to_pay=bank
    )

    data = await state.get_data()
    pending_invite_code = data.get("pending_invite_code")

    await state.clear()

    if pending_invite_code:
        stmt = select(User).filter_by(telegram_id=message.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        table_use_case = TableUseCase(session)
        table = await table_use_case.get_table_by_code(pending_invite_code)

        if table and user:
            result = await session.execute(
                select(TableUser).filter_by(table_id=table.id, user_id=user.id)
            )
            existing = result.scalar_one_or_none()

            if not existing:
                try:
                    await table_use_case.join_table(table.id, user.id)
                    await message.answer(
                        f"🎉 Регистрация завершена!\n\n"
                        f"✅ Вы успешно присоединились к столу '{table.name}'!\n\n"
                        f"Теперь вы можете добавлять расходы и просматривать баланс.",
                        reply_markup=get_main_menu_keyboard()
                    )
                    return
                except Exception:
                    pass

    await message.answer(
        "🎉 Регистрация завершена!\n\n"
        "Теперь вы можете пользоваться ботом 👍",
        reply_markup=get_main_menu_keyboard()
    )

