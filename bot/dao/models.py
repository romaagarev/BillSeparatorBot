from typing import List, Optional
from sqlalchemy import (
    BigInteger,
    Integer,
    Text,
    ForeignKey,
    Boolean,
    Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from bot.dao.database import Base


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[Optional[str]]
    first_name: Mapped[Optional[str]]
    last_name: Mapped[Optional[str]]
    phone_number: Mapped[Optional[str]]
    link_to_pay: Mapped[Optional[str]]
    timezone: Mapped[Optional[str]] = mapped_column(Text, default="Europe/Moscow")

    table_links: Mapped[List["TableUser"]] = relationship(
        "TableUser", back_populates="user", cascade="all, delete-orphan"
    )
    transactions_from: Mapped[List["Transaction"]] = relationship(
        "Transaction",
        foreign_keys="Transaction.user_id_from",
        back_populates="user_from",
        cascade="all, delete-orphan"
    )
    transactions_to: Mapped[List["Transaction"]] = relationship(
        "Transaction",
        foreign_keys="Transaction.user_id_to",
        back_populates="user_to",
        cascade="all, delete-orphan"
    )
    consumptions: Mapped[List["UserItemConsumption"]] = relationship(
        "UserItemConsumption",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User(id={self.id}, tg_id={self.telegram_id}, username={self.username})>"


class DiningTable(Base):
    __tablename__ = "tables"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    invite_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)

    table_items: Mapped[List["TableItem"]] = relationship(
        "TableItem", back_populates="table", cascade="all, delete-orphan"
    )
    items: Mapped[List["Item"]] = relationship(
        "Item", secondary="table_items", back_populates="tables", viewonly=True
    )

    table_users: Mapped[List["TableUser"]] = relationship(
        "TableUser", back_populates="table", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<DiningTable(id={self.id}, name='{self.name}', invite_code='{self.invite_code}')>"


class Item(Base):
    __tablename__ = "items"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    is_income: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    tables: Mapped[List[DiningTable]] = relationship(
        "DiningTable", secondary="table_items", back_populates="items", viewonly=True
    )
    table_items: Mapped[List["TableItem"]] = relationship(
        "TableItem", back_populates="item", cascade="all, delete-orphan"
    )
    consumptions: Mapped[List["UserItemConsumption"]] = relationship(
        "UserItemConsumption", back_populates="item", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Item(id={self.id}, name='{self.name}', price={self.price}, is_income={self.is_income})>"


class TableItem(Base):
    __tablename__ = "table_items"

    table_id: Mapped[int] = mapped_column(ForeignKey("tables.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)

    table: Mapped[DiningTable] = relationship("DiningTable", back_populates="table_items")
    item: Mapped[Item] = relationship("Item", back_populates="table_items")

    def __repr__(self):
        return f"<TableItem(table_id={self.table_id}, item_id={self.item_id}, quantity={self.quantity})>"


class TableUser(Base):
    __tablename__ = "table_user"

    table_id: Mapped[int] = mapped_column(ForeignKey("tables.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    agree_to_close: Mapped[bool] = mapped_column(Boolean, default=False)

    table: Mapped[DiningTable] = relationship("DiningTable", back_populates="table_users")
    user: Mapped[User] = relationship("User", back_populates="table_links")

    def __repr__(self):
        return f"<TableUser(table_id={self.table_id}, user_id={self.user_id}, agree={self.agree_to_close})>"


class Transaction(Base):
    __tablename__ = "transactions"

    table_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tables.id"))
    user_id_from: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user_id_to: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)

    user_from: Mapped[User] = relationship(
        "User", foreign_keys=[user_id_from], back_populates="transactions_from"
    )
    user_to: Mapped[User] = relationship(
        "User", foreign_keys=[user_id_to], back_populates="transactions_to"
    )
    table: Mapped[Optional[DiningTable]] = relationship("DiningTable")

    def __repr__(self):
        return (
            f"<Transaction(id={self.id}, from={self.user_id_from}, "
            f"to={self.user_id_to}, amount={self.amount})>"
        )


class UserItemConsumption(Base):
    __tablename__ = "user_item_consumption"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    ratio: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    user: Mapped[User] = relationship("User", back_populates="consumptions")
    item: Mapped[Item] = relationship("Item", back_populates="consumptions")

    def __repr__(self):
        return f"<UserItemConsumption(user_id={self.user_id}, item_id={self.item_id}, ratio={self.ratio})>"
