"""Set up the database engine and session for the application."""

from asyncio import current_task
from typing import AsyncIterator

from fastapi.concurrency import asynccontextmanager
from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)

from app.db import DB_READ_URI, DB_WRITE_URI
from app.db.base import Base

engine_read = None
engine_write = None


async def init_db() -> None:
    """Initialize the database engine."""
    global engine_read, engine_write

    logger.info('Initializing the database engines...')

    # create the write database engine
    # echo=True logs the queries that are executed, set to False to disable these logs
    logger.debug('Initializing the write db engine with uri: {}', DB_WRITE_URI)
    engine_write = create_async_engine(DB_WRITE_URI, echo=False)

    async with engine_write.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if DB_READ_URI:
        # create the write database engine
        # echo=True logs the queries that are executed, set to False to disable these logs
        logger.debug('Initializing the read db engine with uri: {}', DB_READ_URI)
        engine_read = create_async_engine(DB_READ_URI, echo=False)

        async with engine_write.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close the database engines."""
    if engine_read is not None:
        await engine_read.dispose()

    if engine_write is not None:
        await engine_write.dispose()


def get_db_session(db_engine: AsyncEngine | None, engine_type: str) -> async_sessionmaker[AsyncSession]:
    """Initialize the database async session instance.

    Args:
        db_engine (AsyncEngine): the database engine
        engine_type (str): the type of engine (read or write)

    Returns:
        async_sessionmaker[AsyncSession]: the async session maker

    Raises:
        ValueError: if the db engine is None

    """
    if db_engine is None:
        raise ValueError(f'The db {engine_type} engine has not been initialized. None type received.')

    return async_sessionmaker(bind=db_engine, expire_on_commit=False)


# I believe @asynccontextmanager is not needed here as long as we are using it as a dependency with Depends
# https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/
async def get_read_session() -> AsyncIterator[async_scoped_session[AsyncSession]]:
    """Retrieve an async read session context that self-closes.

    Yields:
        session (async_scoped_session): An asynchronous `read` scoped session

    """
    session = async_scoped_session(
        session_factory=get_db_session(engine_read, 'read'),
        scopefunc=current_task,
    )
    try:
        yield session
    finally:
        await session.close()


@asynccontextmanager
async def get_read_session_with_context() -> AsyncIterator[async_scoped_session[AsyncSession]]:
    """Retrieve an async read session context that self-closes. This should be used when NOT using FastAPI's Depends.

    Yields:
        session (async_scoped_session): An asynchronous `read` scoped session

    """
    session = async_scoped_session(
        session_factory=get_db_session(engine_read, 'read'),
        scopefunc=current_task,
    )
    try:
        yield session
    finally:
        await session.close()


# I believe @asynccontextmanager is not needed here as long as we are using it as a dependency with Depends
# https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/
async def get_write_session() -> AsyncIterator[async_scoped_session[AsyncSession]]:
    """Retrieve an async write session context that self-closes. This should be used when using FastAPI's Depends.

    Yields:
        session (async_scoped_session): An asynchronous `write` scoped session

    """
    session = async_scoped_session(
        session_factory=get_db_session(engine_write, 'write'),
        scopefunc=current_task,
    )
    try:
        yield session
    finally:
        await session.close()


@asynccontextmanager
async def get_write_session_with_context() -> AsyncIterator[async_scoped_session[AsyncSession]]:
    """Retrieve an async write session context that self-closes.

    Yields:
        session (async_scoped_session): An asynchronous `write` scoped session

    """
    session = async_scoped_session(
        session_factory=get_db_session(engine_write, 'write'),
        scopefunc=current_task,
    )
    try:
        yield session
    finally:
        await session.close()
