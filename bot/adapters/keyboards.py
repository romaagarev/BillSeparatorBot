from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu_keyboard():
    keyboard = [
        [KeyboardButton(text="🍽️ Мои столы")],
        [KeyboardButton(text="➕ Создать стол"), KeyboardButton(text="🔗 Присоединиться к столу")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_table_menu_keyboard():
    keyboard = [
        [KeyboardButton(text="➕ Добавить расход")],
        [KeyboardButton(text="💰 Посмотреть баланс"), KeyboardButton(text="👥 Участники")],
        [KeyboardButton(text="📋 История операций"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="🔙 Назад к столам"), KeyboardButton(text="🏠 Главное меню")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_cancel_keyboard():
    keyboard = [
        [KeyboardButton(text="❌ Отмена")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_transaction_type_keyboard():
    """Keyboard for selecting transaction type (expense or income)"""
    keyboard = [
        [
            InlineKeyboardButton(text="💸 Расход", callback_data="expense"),
            InlineKeyboardButton(text="💰 Доход", callback_data="income")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_split_method_keyboard():
    """Keyboard for selecting how to split the amount"""
    keyboard = [
        [InlineKeyboardButton(text="👤 Только на меня", callback_data="split_me")],
        [InlineKeyboardButton(text="👥 Разделить между всеми", callback_data="split_all")],
        [InlineKeyboardButton(text="✏️ Выбрать участников", callback_data="split_custom")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_participants_keyboard(table_users, selected_ids):
    """
    Keyboard for selecting participants
    
    Args:
        table_users: List of tuples (user_id, user_name)
        selected_ids: List of selected user IDs
    """
    keyboard = []
    
    for user_id, user_name in table_users:
        is_selected = user_id in selected_ids
        button_text = f"{'✅' if is_selected else '☐'} {user_name}"
        keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"participant_{user_id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="✔️ Готово", callback_data="participants_done")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_tables_inline_keyboard(tables_list):
    """
    Keyboard for selecting a table from user's tables
    
    Args:
        tables_list: List of tuples (table_id, table_name)
    """
    keyboard = []
    
    for table_id, table_name in tables_list:
        keyboard.append([
            InlineKeyboardButton(
                text=f"🍽️ {table_name}",
                callback_data=f"table_{table_id}"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
