from typing import List, Optional, Dict, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from bot.dao.dao import ItemDao, TableItemDao, UserItemConsumptionDao
from bot.dao.models import User, Item, TableItem, UserItemConsumption, TableUser
from pydantic import BaseModel
from collections import defaultdict


class CreateItemInput(BaseModel):
    name: str
    price: int
    is_income: bool = False
    created_by_id: Optional[int] = None


class CreateTableItemInput(BaseModel):
    table_id: int
    item_id: int


class CreateConsumptionInput(BaseModel):
    user_id: int
    item_id: int
    ratio: float


class ExpenseUseCase:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_expense(self, table_id: int, item_name: str, price: int,
                         user_ids: List[int], ratios: Optional[List[float]] = None,
                         is_income: bool = False, created_by_id: Optional[int] = None) -> int:
        if ratios is None:
            ratios = [1.0] * len(user_ids)
        
        item_data = CreateItemInput(name=item_name, price=price, is_income=is_income, created_by_id=created_by_id)
        item = await ItemDao.add(self.session, item_data)
        item_id = item.id
        
        table_item_data = CreateTableItemInput(table_id=table_id, item_id=item_id)
        await TableItemDao.add(self.session, table_item_data)
        
        for user_id, ratio in zip(user_ids, ratios):
            consumption_data = CreateConsumptionInput(user_id=user_id, item_id=item_id, ratio=ratio)
            await UserItemConsumptionDao.add(self.session, consumption_data)
        
        await self.session.commit()
        return item_id

    async def calculate_debts(self, table_id: int) -> List[Tuple[int, int, int]]:
        result = await self.session.execute(
            select(TableUser.user_id).filter(TableUser.table_id == table_id)
        )
        user_ids = [row[0] for row in result.all()]
        
        if len(user_ids) < 2:
            return []
        
        balances = {}
        
        for user_id in user_ids:
            expenses = await self._calculate_user_amount(user_id, table_id, is_income=False)
            income = await self._calculate_user_amount(user_id, table_id, is_income=True)
            
            balances[user_id] = int(income - expenses)
        
        return self._minimize_transfers(balances)
    
    def _minimize_transfers(self, balances: Dict[int, int]) -> List[Tuple[int, int, int]]:
        transfers = []
        
        creditors = [(user_id, amount) for user_id, amount in balances.items() if amount > 0]
        debtors = [(user_id, -amount) for user_id, amount in balances.items() if amount < 0]
        
        creditors.sort(key=lambda x: x[1], reverse=True)
        debtors.sort(key=lambda x: x[1], reverse=True)
        
        i, j = 0, 0
        while i < len(creditors) and j < len(debtors):
            creditor_id, credit_amount = creditors[i]
            debtor_id, debt_amount = debtors[j]
            
            transfer_amount = min(credit_amount, debt_amount)
            
            if transfer_amount > 0:
                transfers.append((debtor_id, creditor_id, transfer_amount))
            
            creditors[i] = (creditor_id, credit_amount - transfer_amount)
            debtors[j] = (debtor_id, debt_amount - transfer_amount)
            
            if creditors[i][1] == 0:
                i += 1
            if debtors[j][1] == 0:
                j += 1
        
        return transfers

    async def _calculate_user_amount(self, user_id: int, table_id: int, is_income: bool) -> int:
        result = await self.session.execute(
            select(Item.id, Item.price)
            .join(UserItemConsumption, UserItemConsumption.item_id == Item.id)
            .join(TableItem, TableItem.item_id == Item.id)
            .filter(
                UserItemConsumption.user_id == user_id,
                TableItem.table_id == table_id,
                Item.is_income == is_income
            )
        )
        items = result.all()
        
        total_amount = 0
        for item_id, item_price in items:
            result = await self.session.execute(
                select(UserItemConsumption.ratio)
                .filter(UserItemConsumption.item_id == item_id)
            )
            all_ratios = [r[0] for r in result.all()]
            total_ratio = sum(all_ratios)
            
            result = await self.session.execute(
                select(UserItemConsumption.ratio)
                .filter(
                    UserItemConsumption.item_id == item_id,
                    UserItemConsumption.user_id == user_id
                )
            )
            user_ratio = result.scalar()
            
            if total_ratio > 0:
                normalized_ratio = user_ratio / total_ratio
                total_amount += int(item_price * normalized_ratio)
        
        return total_amount

    async def get_user_balance(self, table_id: int, user_id: int) -> Dict[str, int]:
        expenses = await self._calculate_user_amount(user_id, table_id, is_income=False)
        income = await self._calculate_user_amount(user_id, table_id, is_income=True)
        
        return {
            'expenses': expenses,
            'income': income,
            'balance': income - expenses
        }

    async def get_table_operations(self, table_id: int) -> List[Dict]:
        result = await self.session.execute(
            select(Item, TableItem)
            .join(TableItem, TableItem.item_id == Item.id)
            .filter(TableItem.table_id == table_id)
            .order_by(Item.created_at.desc())
        )
        items_data = result.all()
        
        operations = []
        for item, table_item in items_data:
            creator_name = None
            if item.created_by_id:
                result_creator = await self.session.execute(
                    select(User).filter(User.id == item.created_by_id)
                )
                creator = result_creator.scalar_one_or_none()
                if creator:
                    creator_name = creator.first_name or creator.username or f"User {creator.telegram_id}"
            
            result = await self.session.execute(
                select(User, UserItemConsumption)
                .join(UserItemConsumption, UserItemConsumption.user_id == User.id)
                .filter(UserItemConsumption.item_id == item.id)
            )
            participants_data = result.all()
            
            participants = []
            for user, consumption in participants_data:
                participants.append({
                    'name': user.first_name or user.username or f"User {user.telegram_id}",
                    'ratio': consumption.ratio
                })
            
            operations.append({
                'id': item.id,
                'name': item.name,
                'price': item.price,
                'is_income': item.is_income,
                'created_at': item.created_at,
                'created_by': creator_name,
                'participants': participants
            })
        
        return operations