from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.adapters.keyboards import get_main_menu_keyboard
from bot.use_cases.user_use_cases import UserUseCase
from bot.use_cases.table_use_cases import TableUseCase

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    
    user_use_case = UserUseCase(session)
    await user_use_case.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    command_args = message.text.split(maxsplit=1)
    if len(command_args) > 1 and command_args[1].startswith("join_"):
        invite_code = command_args[1][5:]
        
        from bot.use_cases.table_use_cases import TableUseCase
        from sqlalchemy import select
        from bot.dao.models import User, TableUser
        
        result = await session.execute(
            select(User).filter_by(telegram_id=message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("Ошибка: пользователь не найден. Попробуйте /start")
            return
        
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
        "Я бот для разделения счетов. Я помогу тебе:\n"
        "• Создавать столы для совместных расходов\n"
        "• Добавлять траты и делить их между участниками\n"
        "• Рассчитывать, кто и сколько должен\n\n"
        "Выбери действие из меню:",
        reply_markup=get_main_menu_keyboard()
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>Помощь по использованию бота</b>\n\n"
        "<b>Основные команды:</b>\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать эту справку\n\n"
        "<b>Как пользоваться:</b>\n"
        "1. Создайте стол для совместных расходов\n"
        "2. Пригласите друзей по ID стола\n"
        "3. Добавляйте расходы и делите их между участниками\n"
        "4. Смотрите баланс и статистику\n\n"
        "Используйте кнопки меню для навигации!",
        parse_mode="HTML"
    )


@router.message(F.text == "🔙 Назад в главное меню")
async def back_to_main_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_menu_keyboard()
    )