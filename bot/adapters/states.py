from aiogram.fsm.state import State, StatesGroup


class TableStates(StatesGroup):
    waiting_for_table_name = State()
    waiting_for_table_id = State()


class ExpenseStates(StatesGroup):
    choosing_type = State()
    waiting_for_item_name = State()
    waiting_for_item_price = State()
    choosing_split_method = State()
    selecting_participants = State()
    entering_ratios = State()