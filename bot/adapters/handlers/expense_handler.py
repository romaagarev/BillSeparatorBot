from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.adapters.keyboards import (
    get_cancel_keyboard, 
    get_table_menu_keyboard,
    get_transaction_type_keyboard,
    get_split_method_keyboard,
    get_participants_keyboard
)
from bot.adapters.states import ExpenseStates
from bot.use_cases.expense_use_cases import ExpenseUseCase

router = Router()


@router.message(F.text == "➕ Добавить расход")
async def add_expense_start(message: Message, state: FSMContext):
    data = await state.get_data()
    current_table_id = data.get("current_table_id")
    
    if not current_table_id:
        await message.answer(
            "Сначала выберите стол из списка 'Мои столы'",
            reply_markup=get_table_menu_keyboard()
        )
        return
    
    await state.set_state(ExpenseStates.choosing_type)
    await message.answer(
        "Выберите тип операции:",
        reply_markup=get_transaction_type_keyboard()
    )


@router.callback_query(ExpenseStates.choosing_type, F.data.in_(["expense", "income"]))
async def transaction_type_selected(callback: CallbackQuery, state: FSMContext):
    is_income = callback.data == "income"
    await state.update_data(is_income=is_income)
    
    transaction_type = "оплаты" if is_income else "расхода"
    await state.set_state(ExpenseStates.waiting_for_item_name)
    await callback.message.edit_text(
        f"Введите название {transaction_type} (например, '{'Чек в ресторане' if is_income else 'Пицца'}'):"
    )
    await callback.message.answer(
        "Введите название:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(ExpenseStates.waiting_for_item_name)
async def add_expense_name(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Операция отменена.", reply_markup=get_table_menu_keyboard())
        return
    
    await state.update_data(item_name=message.text)
    await state.set_state(ExpenseStates.waiting_for_item_price)
    
    data = await state.get_data()
    is_income = data.get("is_income", False)
    transaction_type = "оплаты" if is_income else "расхода"
    
    await message.answer(
        f"Введите сумму {transaction_type} в рублях (например, 1500):",
        reply_markup=get_cancel_keyboard()
    )


@router.message(ExpenseStates.waiting_for_item_price)
async def add_expense_price(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Операция отменена.", reply_markup=get_table_menu_keyboard())
        return
    
    try:
        price = int(float(message.text) * 100)
    except ValueError:
        await message.answer("Неверный формат цены. Введите число:")
        return
    
    await state.update_data(price=price)
    
    data = await state.get_data()
    current_table_id = data.get("current_table_id")
    
    from sqlalchemy import select
    from bot.dao.models import User, TableUser
    
    result = await session.execute(
        select(User).filter_by(telegram_id=message.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await message.answer("Ошибка: пользователь не найден.")
        return
    
    result = await session.execute(
        select(User)
        .join(TableUser, TableUser.user_id == User.id)
        .filter(TableUser.table_id == current_table_id)
    )
    table_users = result.scalars().all()
    
    await state.update_data(table_users=[(u.id, u.first_name or u.username or f"User {u.telegram_id}") for u in table_users])
    
    await state.set_state(ExpenseStates.choosing_split_method)
    await message.answer(
        "Как разделить сумму?",
        reply_markup=get_split_method_keyboard()
    )


@router.callback_query(ExpenseStates.choosing_split_method, F.data == "split_all")
async def split_all_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    item_name = data.get("item_name")
    price = data.get("price")
    current_table_id = data.get("current_table_id")
    is_income = data.get("is_income", False)
    table_users = data.get("table_users", [])
    
    user_ids = [u[0] for u in table_users]
    
    from sqlalchemy import select
    from bot.dao.models import User
    
    result = await session.execute(
        select(User).filter_by(telegram_id=callback.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    expense_use_case = ExpenseUseCase(session)
    await expense_use_case.add_expense(
        table_id=current_table_id,
        item_name=item_name,
        price=price,
        user_ids=user_ids,
        is_income=is_income,
        created_by_id=user.id if user else None
    )
    
    await state.set_state(None)
    
    transaction_type = "Оплата" if is_income else "Расход"
    await callback.message.edit_text(
        f"✅ {transaction_type} '{item_name}' на сумму {price/100:.2f} ₽ добавлен!\n"
        f"Сумма разделена поровну между {len(user_ids)} участниками."
    )
    await callback.message.answer(
        "Операция завершена.",
        reply_markup=get_table_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(ExpenseStates.choosing_split_method, F.data == "split_me")
async def split_me_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    item_name = data.get("item_name")
    price = data.get("price")
    current_table_id = data.get("current_table_id")
    is_income = data.get("is_income", False)
    
    from sqlalchemy import select
    from bot.dao.models import User
    
    result = await session.execute(
        select(User).filter_by(telegram_id=callback.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await callback.message.edit_text("Ошибка: пользователь не найден.")
        await callback.answer()
        return
    
    expense_use_case = ExpenseUseCase(session)
    await expense_use_case.add_expense(
        table_id=current_table_id,
        item_name=item_name,
        price=price,
        user_ids=[user.id],
        is_income=is_income,
        created_by_id=user.id
    )
    
    await state.set_state(None)
    
    transaction_type = "Оплата" if is_income else "Расход"
    await callback.message.edit_text(
        f"✅ {transaction_type} '{item_name}' на сумму {price/100:.2f} ₽ добавлен!\n"
        f"Сумма записана только на вас."
    )
    await callback.message.answer(
        "Операция завершена.",
        reply_markup=get_table_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(ExpenseStates.choosing_split_method, F.data == "split_custom")
async def split_custom_selected(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    table_users = data.get("table_users", [])
    
    await state.update_data(selected_participants=[])
    await state.set_state(ExpenseStates.selecting_participants)
    
    await callback.message.edit_text(
        "Выберите участников для разделения суммы:\n"
        "(Нажмите 'Готово' когда закончите выбор)",
        reply_markup=get_participants_keyboard(table_users, [])
    )
    await callback.answer()


@router.callback_query(ExpenseStates.selecting_participants, F.data.startswith("participant_"))
async def toggle_participant(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[1])
    data = await state.get_data()
    selected = data.get("selected_participants", [])
    table_users = data.get("table_users", [])
    
    if user_id in selected:
        selected.remove(user_id)
    else:
        selected.append(user_id)
    
    await state.update_data(selected_participants=selected)
    
    await callback.message.edit_reply_markup(
        reply_markup=get_participants_keyboard(table_users, selected)
    )
    await callback.answer()


@router.callback_query(ExpenseStates.selecting_participants, F.data == "participants_done")
async def participants_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_participants", [])
    
    if not selected:
        await callback.answer("Выберите хотя бы одного участника!", show_alert=True)
        return
    
    await state.set_state(ExpenseStates.entering_ratios)
    
    table_users = data.get("table_users", [])
    selected_names = [name for uid, name in table_users if uid in selected]
    
    await callback.message.edit_text(
        f"Выбрано участников: {len(selected)}\n\n"
        f"Введите доли для каждого участника через пробел (например: 1 2 1).\n"
        f"Или введите 'поровну' для равного разделения.\n\n"
        f"Участники:\n" + "\n".join([f"{i+1}. {name}" for i, name in enumerate(selected_names)])
    )
    await callback.message.answer(
        "Введите доли:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(ExpenseStates.entering_ratios)
async def ratios_entered(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Операция отменена.", reply_markup=get_table_menu_keyboard())
        return
    
    data = await state.get_data()
    selected = data.get("selected_participants", [])
    item_name = data.get("item_name")
    price = data.get("price")
    current_table_id = data.get("current_table_id")
    is_income = data.get("is_income", False)
    
    if message.text.lower() == "поровну":
        ratios = [1.0] * len(selected)
    else:
        try:
            ratios = [float(x) for x in message.text.split()]
            if len(ratios) != len(selected):
                await message.answer(
                    f"Ошибка: нужно ввести {len(selected)} долей, а вы ввели {len(ratios)}.\n"
                    "Попробуйте снова:"
                )
                return
        except ValueError:
            await message.answer("Неверный формат. Введите числа через пробел или 'поровну':")
            return
    
    from sqlalchemy import select
    from bot.dao.models import User
    
    result = await session.execute(
        select(User).filter_by(telegram_id=message.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    expense_use_case = ExpenseUseCase(session)
    await expense_use_case.add_expense(
        table_id=current_table_id,
        item_name=item_name,
        price=price,
        user_ids=selected,
        ratios=ratios,
        is_income=is_income,
        created_by_id=user.id if user else None
    )
    
    await state.set_state(None)
    
    transaction_type = "Оплата" if is_income else "Расход"
    await message.answer(
        f"✅ {transaction_type} '{item_name}' на сумму {price/100:.2f} ₽ добавлен!\n"
        f"Сумма разделена между {len(selected)} участниками с указанными долями.",
        reply_markup=get_table_menu_keyboard()
    )


@router.message(F.text == "💰 Посмотреть баланс")
async def view_balance(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    current_table_id = data.get("current_table_id")
    
    if not current_table_id:
        await message.answer(
            "Сначала выберите стол из списка 'Мои столы'",
            reply_markup=get_table_menu_keyboard()
        )
        return
    
    from sqlalchemy import select
    from bot.dao.models import User
    
    result = await session.execute(
        select(User).filter_by(telegram_id=message.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await message.answer("Ошибка: пользователь не найден.")
        return
    
    expense_use_case = ExpenseUseCase(session)
    balance_data = await expense_use_case.get_user_balance(current_table_id, user.id)
    debts = await expense_use_case.calculate_debts(current_table_id)
    
    text = "💰 Ваш баланс:\n\n"
    text += f"Расходы: {balance_data['expenses']/100:.2f} ₽\n"
    text += f"Оплаты: {balance_data['income']/100:.2f} ₽\n"
    text += f"Баланс: {balance_data['balance']/100:.2f} ₽\n\n"
    
    if debts:
        text += "📊 Минимизированные переводы:\n\n"
        
        result = await session.execute(
            select(User)
        )
        users_dict = {u.id: (u.first_name or u.username or f"User {u.telegram_id}") for u in result.scalars().all()}
        
        for from_id, to_id, amount in debts:
            from_name = users_dict.get(from_id, f"User {from_id}")
            to_name = users_dict.get(to_id, f"User {to_id}")
            
            if from_id == user.id:
                text += f"➡️ Вы должны {to_name}: {amount/100:.2f} ₽\n"
            elif to_id == user.id:
                text += f"⬅️ {from_name} должен вам: {amount/100:.2f} ₽\n"
            else:
                text += f"• {from_name} → {to_name}: {amount/100:.2f} ₽\n"
    else:
        text += "✅ Все расчеты завершены!"
    
    await message.answer(text, reply_markup=get_table_menu_keyboard())

@router.message(F.text == "💳 Посчитать долги")
async def calculate_debts_handler(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    current_table_id = data.get("current_table_id")
    
    if not current_table_id:
        await message.answer(
            "Сначала выберите стол из списка 'Мои столы'",
            reply_markup=get_table_menu_keyboard()
        )
        return
    
    expense_use_case = ExpenseUseCase(session)
    debts = await expense_use_case.calculate_debts(current_table_id)
    
    if not debts:
        await message.answer(
            "✅ Все расчеты завершены! Никто никому ничего не должен.",
            reply_markup=get_table_menu_keyboard()
        )
        return
    
    from sqlalchemy import select
    from bot.dao.models import User
    
    result = await session.execute(select(User))
    users_dict = {u.id: (u.first_name or u.username or f"User {u.telegram_id}") for u in result.scalars().all()}
    
    text = "💳 <b>Минимизированные переводы для закрытия долгов:</b>\n\n"
    
    for from_id, to_id, amount in debts:
        from_name = users_dict.get(from_id, f"User {from_id}")
        to_name = users_dict.get(to_id, f"User {to_id}")
        text += f"➡️ <b>{from_name}</b> → <b>{to_name}</b>: {amount/100:.2f} ₽\n"
    
    text += f"\n<i>Всего переводов: {len(debts)}</i>"
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_table_menu_keyboard())



@router.message(F.text == "👥 Участники")
async def view_participants(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    current_table_id = data.get("current_table_id")
    
    if not current_table_id:
        await message.answer(
            "Сначала выберите стол из списка 'Мои столы'",
            reply_markup=get_table_menu_keyboard()
        )
        return
    
    from sqlalchemy import select
    from bot.dao.models import TableUser, User, DiningTable
    
    result = await session.execute(
        select(DiningTable).filter(DiningTable.id == current_table_id)
    )
    table = result.scalar_one_or_none()
    
    if not table:
        await message.answer("Ошибка: стол не найден.")
        return
    
    table_name = table.name
    invite_code = table.invite_code
    
    result = await session.execute(
        select(TableUser, User)
        .join(User, TableUser.user_id == User.id)
        .filter(TableUser.table_id == current_table_id)
    )
    participants = result.all()
    
    if not participants:
        await message.answer("В этом столе пока нет участников.")
        return
    
    bot = message.bot
    bot_username = (await bot.me()).username
    invite_link = f"https://t.me/{bot_username}?start=join_{invite_code}"
    
    text = f"🍽️ <b>Стол: {table_name}</b>\n\n"
    text += "👥 <b>Участники:</b>\n\n"
    for i, (table_user, user) in enumerate(participants, 1):
        name = user.first_name or user.username or f"User {user.telegram_id}"
        if user.username:
            text += f"{i}. {name} (@{user.username})\n"
        else:
            text += f"{i}. {name}\n"
    
    text += f"\n🔗 <b>Ссылка для приглашения:</b>\n{invite_link}\n\n"
    text += f"🔑 <b>Код приглашения:</b> <code>{invite_code}</code>\n\n"
    text += "<i>Отправьте ссылку или код друзьям, чтобы они присоединились к столу</i>"
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_table_menu_keyboard())


@router.message(F.text == "📊 Статистика")
async def view_statistics(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    current_table_id = data.get("current_table_id")
    
    if not current_table_id:
        await message.answer(
            "Сначала выберите стол из списка 'Мои столы'",
            reply_markup=get_table_menu_keyboard()
        )
        return
    
    from sqlalchemy import select, func
    from bot.dao.models import Item, TableItem
    
    result = await session.execute(
        select(
            func.count(Item.id).label('total_items'),
            func.sum(Item.price).filter(Item.is_income == False).label('total_expenses'),
            func.sum(Item.price).filter(Item.is_income == True).label('total_income')
        )
        .join(TableItem, TableItem.item_id == Item.id)
        .filter(TableItem.table_id == current_table_id)
    )
    stats = result.one()
    
    total_items = stats.total_items or 0
    total_expenses = stats.total_expenses or 0
    total_income = stats.total_income or 0
    
    text = "📊 Статистика стола:\n\n"
    text += f"Всего операций: {total_items}\n"
    text += f"Общие расходы: {total_expenses/100:.2f} ₽\n"
    text += f"Общие оплаты: {total_income/100:.2f} ₽\n"
    text += f"Итоговый баланс: {(total_income - total_expenses)/100:.2f} ₽\n"
    
    await message.answer(text, reply_markup=get_table_menu_keyboard())


@router.message(F.text == "📋 История операций")
async def view_operations_history(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    current_table_id = data.get("current_table_id")
    
    if not current_table_id:
        await message.answer(
            "Сначала выберите стол из списка 'Мои столы'",
            reply_markup=get_table_menu_keyboard()
        )
        return
    
    from sqlalchemy import select
    from bot.dao.models import User
    from datetime import datetime, timezone, timedelta
    
    result = await session.execute(
        select(User).filter_by(telegram_id=message.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    user_tz_offset = timedelta(hours=3)
    user_timezone = timezone(user_tz_offset)
    
    expense_use_case = ExpenseUseCase(session)
    operations = await expense_use_case.get_table_operations(current_table_id)
    
    if not operations:
        await message.answer(
            "📋 История операций пуста.\n\n"
            "Добавьте первую операцию, чтобы начать отслеживать расходы и оплаты!",
            reply_markup=get_table_menu_keyboard()
        )
        return
    
    text = "📋 <b>История операций:</b>\n\n"
    
    for i, op in enumerate(operations, 1):
        operation_type = "💰 Оплата" if op['is_income'] else "💸 Расход"
        if op['created_at']:
            utc_time = op['created_at'].replace(tzinfo=timezone.utc)
            local_time = utc_time.astimezone(user_timezone)
            date_str = local_time.strftime("%d.%m.%Y %H:%M")
        else:
            date_str = "Дата неизвестна"
        
        text += f"<b>{i}. {operation_type}: {op['name']}</b>\n"
        text += f"   Сумма: {op['price']/100:.2f} ₽\n"
        text += f"   Дата: {date_str}\n"
        
        if op.get('created_by'):
            text += f"   Добавил: {op['created_by']}\n"
        
        if op['participants']:
            total_ratio = sum(p['ratio'] for p in op['participants'])
            text += "   Участники:\n"
            for p in op['participants']:
                normalized_ratio = p['ratio'] / total_ratio if total_ratio > 0 else 0
                participant_amount = op['price'] * normalized_ratio / 100
                text += f"      • {p['name']}: {participant_amount:.2f} ₽"
                if len(op['participants']) > 1 and p['ratio'] != 1.0:
                    text += f" (доля {p['ratio']:.1f})"
                text += "\n"
        
        text += "\n"
    
    if len(text) > 4000:
        parts = []
        current_part = "📋 <b>История операций:</b>\n\n"
        
        for i, op in enumerate(operations, 1):
            operation_type = "💰 Оплата" if op['is_income'] else "💸 Расход"
            if op['created_at']:
                utc_time = op['created_at'].replace(tzinfo=timezone.utc)
                local_time = utc_time.astimezone(user_timezone)
                date_str = local_time.strftime("%d.%m.%Y %H:%M")
            else:
                date_str = "Дата неизвестна"
            
            op_text = f"<b>{i}. {operation_type}: {op['name']}</b>\n"
            op_text += f"   Сумма: {op['price']/100:.2f} ₽\n"
            op_text += f"   Дата: {date_str}\n"
            
            if op.get('created_by'):
                op_text += f"   Добавил: {op['created_by']}\n"
            
            if op['participants']:
                total_ratio = sum(p['ratio'] for p in op['participants'])
                op_text += "   Участники:\n"
                for p in op['participants']:
                    normalized_ratio = p['ratio'] / total_ratio if total_ratio > 0 else 0
                    participant_amount = op['price'] * normalized_ratio / 100
                    op_text += f"      • {p['name']}: {participant_amount:.2f} ₽"
                    if len(op['participants']) > 1 and p['ratio'] != 1.0:
                        op_text += f" (доля {p['ratio']:.1f})"
                    op_text += "\n"
            
            op_text += "\n"
            
            if len(current_part) + len(op_text) > 4000:
                parts.append(current_part)
                current_part = op_text
            else:
                current_part += op_text
        
        if current_part:
            parts.append(current_part)
        
        for part in parts:
            await message.answer(part, parse_mode="HTML")
        
        await message.answer(
            f"Всего операций: {len(operations)}",
            reply_markup=get_table_menu_keyboard()
        )
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_table_menu_keyboard())