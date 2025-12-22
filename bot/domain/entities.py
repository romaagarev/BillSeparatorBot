from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime


@dataclass
class UserEntity:
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    link_to_pay: Optional[str] = None
    id: Optional[int] = None


@dataclass
class TableEntity:
    name: str
    id: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class ItemEntity:
    name: str
    price: int
    is_income: bool = False
    id: Optional[int] = None


@dataclass
class ExpenseEntity:
    item: ItemEntity
    participants: List[UserEntity]
    ratios: List[float]


@dataclass
class DebtEntity:
    from_user: UserEntity
    to_user: UserEntity
    amount: int