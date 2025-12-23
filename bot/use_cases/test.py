import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from bot.dao.database import Base
from sqlalchemy import select

from bot.dao.database import Base
from bot.dao.models import User, DiningTable, TableUser, UserItemConsumption, Item
from bot.use_cases.table_use_cases import TableUseCase
from bot.use_cases.expense_use_cases import ExpenseUseCase
from bot.use_cases.user_use_cases import UserUseCase
from bot.domain.entities import TableEntity

pytestmark = pytest.mark.asyncio

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine(DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def user(db_session: AsyncSession) -> User:
    user = User(
        telegram_id=123456789,
        username="testuser",
        first_name="Test",
        last_name="User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession) -> User:
    user = User(
        telegram_id=987654321,
        username="otheruser",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def test_generate_invite_code_length_and_charset():
    usecase = TableUseCase(None)

    code = usecase._generate_invite_code(length=12)

    assert len(code) == 12
    assert all(c.isupper() or c.isdigit() for c in code)


@pytest.mark.asyncio
async def test_is_invite_code_unique_true(db_session, user):
    usecase = TableUseCase(db_session)

    result = await usecase._is_invite_code_unique("UNIQUE123")
    assert result is True


@pytest.mark.asyncio
async def test_is_invite_code_unique_false(db_session, user):
    table = DiningTable(name="Table", invite_code="DUPLICATE")
    db_session.add(table)
    await db_session.commit()

    usecase = TableUseCase(db_session)
    result = await usecase._is_invite_code_unique("DUPLICATE")

    assert result is False


@pytest.mark.asyncio
async def test_create_table_creates_table_and_creator_link(db_session, user):
    usecase = TableUseCase(db_session)

    table_id, invite_code = await usecase.create_table(
        name="Dinner",
        creator_id=user.id,
    )

    table = await db_session.get(DiningTable, table_id)
    assert table is not None
    assert table.name == "Dinner"
    assert table.invite_code == invite_code

    link = await db_session.execute(
        select(TableUser).where(
            TableUser.table_id == table_id,
            TableUser.user_id == user.id,
        )
    )
    assert link.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_create_table_invite_code_is_unique(db_session, user):
    usecase = TableUseCase(db_session)

    _, code1 = await usecase.create_table("A", user.id)
    _, code2 = await usecase.create_table("B", user.id)

    assert code1 != code2


@pytest.mark.asyncio
async def test_join_table_adds_user(db_session, user, other_user):
    usecase = TableUseCase(db_session)

    table_id, _ = await usecase.create_table("Party", user.id)

    result = await usecase.join_table(table_id, other_user.id)
    assert result is True

    link = await db_session.execute(
        select(TableUser).where(
            TableUser.table_id == table_id,
            TableUser.user_id == other_user.id,
        )
    )
    assert link.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_join_table_by_code_success(db_session, user, other_user):
    usecase = TableUseCase(db_session)

    table_id, code = await usecase.create_table("Lunch", user.id)

    result = await usecase.join_table_by_code(code, other_user.id)
    assert result == table_id

    link = await db_session.execute(
        select(TableUser).where(
            TableUser.table_id == table_id,
            TableUser.user_id == other_user.id,
        )
    )
    assert link.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_join_table_by_code_not_found(db_session, user):
    usecase = TableUseCase(db_session)

    result = await usecase.join_table_by_code("INVALIDCODE", user.id)
    assert result is None


@pytest.mark.asyncio
async def test_get_table_by_code_found(db_session, user):
    usecase = TableUseCase(db_session)

    table_id, code = await usecase.create_table("Cafe", user.id)

    table = await usecase.get_table_by_code(code)
    assert table is not None
    assert table.id == table_id


@pytest.mark.asyncio
async def test_get_table_by_code_not_found(db_session):
    usecase = TableUseCase(db_session)

    table = await usecase.get_table_by_code("NOPE")
    assert table is None


@pytest.mark.asyncio
async def test_get_user_tables_returns_all_tables(db_session, user):
    usecase = TableUseCase(db_session)

    t1_id, _ = await usecase.create_table("Table 1", user.id)
    t2_id, _ = await usecase.create_table("Table 2", user.id)

    tables = await usecase.get_user_tables(user.id)

    assert len(tables) == 2
    assert all(isinstance(t, TableEntity) for t in tables)

    ids = {t.id for t in tables}
    assert ids == {t1_id, t2_id}


@pytest_asyncio.fixture
async def users(db_session):
    users = [
        User(telegram_id=1, first_name="Alice"),
        User(telegram_id=2, first_name="Bob"),
        User(telegram_id=3, first_name="Charlie"),
    ]
    db_session.add_all(users)
    await db_session.commit()
    for u in users:
        await db_session.refresh(u)
    return users


@pytest_asyncio.fixture
async def table(db_session, users):
    table = DiningTable(name="Dinner", invite_code="TABLE123")
    db_session.add(table)
    await db_session.commit()
    await db_session.refresh(table)

    for user in users:
        db_session.add(TableUser(table_id=table.id, user_id=user.id))

    await db_session.commit()
    return table


@pytest.mark.asyncio
async def test_add_expense_creates_item_and_consumptions(db_session, table, users):
    usecase = ExpenseUseCase(db_session)

    item_id = await usecase.add_expense(
        table_id=table.id,
        item_name="Pizza",
        price=300,
        user_ids=[u.id for u in users],
    )

    item = await db_session.get(Item, item_id)
    assert item is not None
    assert item.name == "Pizza"
    assert item.price == 300
    assert item.is_income is False

    result = await db_session.execute(
        select(UserItemConsumption).filter(
            UserItemConsumption.item_id == item_id
        )
    )
    consumptions = result.scalars().all()
    assert len(consumptions) == 3


@pytest.mark.asyncio
async def test_add_expense_with_custom_ratios(db_session, table, users):
    usecase = ExpenseUseCase(db_session)

    item_id = await usecase.add_expense(
        table_id=table.id,
        item_name="Wine",
        price=300,
        user_ids=[users[0].id, users[1].id],
        ratios=[2.0, 1.0],
    )

    result = await db_session.execute(
        select(UserItemConsumption.ratio).filter(
            UserItemConsumption.item_id == item_id
        )
    )
    ratios = sorted(r[0] for r in result.all())
    assert ratios == [1.0, 2.0]


@pytest.mark.asyncio
async def test_calculate_user_amount_expense(db_session, table, users):
    usecase = ExpenseUseCase(db_session)

    await usecase.add_expense(
        table_id=table.id,
        item_name="Dinner",
        price=300,
        user_ids=[u.id for u in users],
    )

    amount = await usecase._calculate_user_amount(
        user_id=users[0].id,
        table_id=table.id,
        is_income=False,
    )

    assert amount == 100


@pytest.mark.asyncio
async def test_calculate_user_amount_income(db_session, table, users):
    usecase = ExpenseUseCase(db_session)

    await usecase.add_expense(
        table_id=table.id,
        item_name="Refund",
        price=300,
        user_ids=[users[0].id],
        is_income=True,
    )

    income = await usecase._calculate_user_amount(
        user_id=users[0].id,
        table_id=table.id,
        is_income=True,
    )

    assert income == 300


@pytest.mark.asyncio
async def test_get_user_balance(db_session, table, users):
    usecase = ExpenseUseCase(db_session)

    await usecase.add_expense(
        table_id=table.id,
        item_name="Food",
        price=300,
        user_ids=[u.id for u in users],
    )

    await usecase.add_expense(
        table_id=table.id,
        item_name="Payback",
        price=150,
        user_ids=[users[0].id],
        is_income=True,
    )

    balance = await usecase.get_user_balance(table.id, users[0].id)

    assert balance["expenses"] == 100
    assert balance["income"] == 150
    assert balance["balance"] == 50


@pytest.mark.asyncio
async def test_calculate_debts_simple(db_session, table, users):
    usecase = ExpenseUseCase(db_session)
    await usecase.add_expense(
        table_id=table.id,
        item_name="Hotel",
        price=300,
        user_ids=[users[0].id],
        is_income=True,
    )

    await usecase.add_expense(
        table_id=table.id,
        item_name="Hotel",
        price=300,
        user_ids=[u.id for u in users],
    )

    debts = await usecase.calculate_debts(table.id)

    assert len(debts) == 2
    debtors = {d[0] for d in debts}
    creditor = debts[0][1]

    assert creditor == users[0].id
    assert debtors == {users[1].id, users[2].id}


@pytest.mark.asyncio
async def test_calculate_debts_single_user(db_session, table, users):
    usecase = ExpenseUseCase(db_session)

    debts = await usecase.calculate_debts(table.id)
    assert debts == []


def test_minimize_transfers_internal():
    balances = {
        1: 100,
        2: -30,
        3: -70,
    }

    usecase = ExpenseUseCase(None)
    transfers = usecase._minimize_transfers(balances)

    assert len(transfers) == 2
    assert sum(t[2] for t in transfers) == 100
    remaining = balances.copy()
    for debtor, creditor, amount in transfers:
        assert amount > 0
        remaining[debtor] += amount
        remaining[creditor] -= amount

    assert all(v == 0 for v in remaining.values())


def test_minimize_transfers_minimal_number_of_transfers_complex():
        balances = {
            1: 300,
            2: 200,
            3: 100,
            4: -250,
            5: -200,
            6: -150,
        }

        usecase = ExpenseUseCase(None)
        transfers = usecase._minimize_transfers(balances)

        assert len(transfers) == 5

        remaining = balances.copy()
        for debtor, creditor, amount in transfers:
            assert amount > 0
            remaining[debtor] += amount
            remaining[creditor] -= amount

        assert all(v == 0 for v in remaining.values())
        for debtor, creditor, _ in transfers:
            assert balances[debtor] < 0
            assert balances[creditor] > 0


@pytest.mark.asyncio
async def test_get_table_operations(db_session, table, users):
    usecase = ExpenseUseCase(db_session)

    await usecase.add_expense(
        table_id=table.id,
        item_name="Pizza",
        price=300,
        user_ids=[users[0].id, users[1].id],
        created_by_id=users[0].id,
    )

    operations = await usecase.get_table_operations(table.id)

    assert len(operations) == 1

    op = operations[0]
    assert op["name"] == "Pizza"
    assert op["price"] == 300
    assert op["created_by"] == "Alice"
    assert len(op["participants"]) == 2


@pytest_asyncio.fixture
async def usecase(db_session):
    return UserUseCase(db_session)


@pytest.mark.asyncio
async def test_get_or_create_user_creates_new(db_session, usecase):
    user_id = await usecase.get_or_create_user(
        telegram_id=123456,
        username="alice",
        first_name="Alice",
        last_name="Smith",
    )

    user = await db_session.get(User, user_id)
    assert user is not None
    assert user.telegram_id == 123456
    assert user.username == "alice"
    assert user.first_name == "Alice"
    assert user.last_name == "Smith"


@pytest.mark.asyncio
async def test_get_or_create_user_returns_existing(db_session, usecase):
    new_user = User(telegram_id=999, username="bob", first_name="Bob")
    db_session.add(new_user)
    await db_session.commit()
    await db_session.refresh(new_user)

    user_id = await usecase.get_or_create_user(
        telegram_id=999,
        username="ignored",
        first_name="Ignored",
        last_name="Ignored",
    )

    assert user_id == new_user.id
    result = await db_session.execute(select(User).filter(User.telegram_id == 999))
    users = result.scalars().all()
    assert len(users) == 1


@pytest.mark.asyncio
async def test_get_or_create_multiple_users(db_session, usecase):
    ids = []
    for i in range(1000):
        user_id = await usecase.get_or_create_user(
            telegram_id=1000 + i,
            username=f"user{i}",
            first_name=f"User{i}",
        )
        ids.append(user_id)

    result = await db_session.execute(select(User))
    users = result.scalars().all()
    assert len(users) == 1000
    assert sorted([u.id for u in users]) == sorted(ids)


@pytest.mark.asyncio
async def test_get_or_create_user_commit(db_session, usecase):
    result = await db_session.execute(select(User))
    assert result.scalars().all() == []

    await usecase.get_or_create_user(telegram_id=555, username="committest")
    result = await db_session.execute(select(User))
    users = result.scalars().all()
    assert len(users) == 1
    assert users[0].telegram_id == 555
