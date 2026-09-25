import asyncio
import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator
import httpx
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Set test environment variables before importing app
os.environ["ADMIN_PASSWORD"] = "test_password_123"
os.environ["BOT_TOKEN"] = "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ"
os.environ["DATA_DIR"] = "./data_test"
os.environ["DATABASE_URL"] = ""

from app.database import Base, get_db_session
from app.server import app
from app import config

TEST_ENGINE = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=TEST_ENGINE,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await TEST_ENGINE.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    resp = await client.post("/api/auth/login", json={"pin": config.ADMIN_PASSWORD})
    assert resp.status_code == 200
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}
