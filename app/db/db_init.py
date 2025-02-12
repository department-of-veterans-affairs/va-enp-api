"""Set up the database engine and session for the application."""

from asyncio import current_task
from typing import AsyncIterator

from fastapi.concurrency import asynccontextmanager
from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)

from app.db import API_DB_READ_URI, API_DB_WRITE_URI, DB_READ_URI, DB_WRITE_URI
from app.db.base import Base

_engine_read = None
_engine_write = None
_engine_api_read = None
_engine_api_write = None


async def init_db() -> None:
    """Initialize the database engine."""
    logger.info('Initializing the database engines...')

    # Without this import, Base.metatable (used below) will not point to any tables, and the
    # call to "run_sync" will not create anything.
    import app.db.models  # noqa

    global _engine_read
    global _engine_write
    global _engine_api_read
    global _engine_api_write

    _engine_read = create_async_engine(DB_READ_URI, echo=False)
    _engine_write = create_async_engine(DB_WRITE_URI, echo=False)
    _engine_api_read = create_async_engine(API_DB_READ_URI, echo=False)
    _engine_api_write = create_async_engine(API_DB_WRITE_URI, echo=False)

    await init_enp_engine(_engine_read)
    await init_enp_engine(_engine_write)


async def init_enp_engine(engine: AsyncEngine) -> None:
    """Initialize the database engine for the ENP database.

    Args:
        engine (AsyncEngine): the database engine

    """
    # echo=True logs the queries that are executed.  Set it to False to disable these logs.
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
        except IntegrityError:  # pragma: no cover
            # Async workers on a fresh container will try to create tables at the same time - No deployed impact
            pass


async def close_db() -> None:
    """Close the database engines."""
    if _engine_read is not None:
        await _engine_read.dispose()

    if _engine_write is not None:
        await _engine_write.dispose()

    if _engine_api_read is not None:
        await _engine_api_read.dispose()

    if _engine_api_write is not None:
        await _engine_api_write.dispose()


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
async def get_read_session_with_depends() -> AsyncIterator[async_scoped_session[AsyncSession]]:
    """Retrieve an async read session context that self-closes.

    Yields:
        session (async_scoped_session): An asynchronous `read` scoped session

    """
    session = async_scoped_session(
        session_factory=get_db_session(_engine_read, 'read'),
        scopefunc=current_task,
    )
    try:
        yield session
    finally:
        await session.close()


async def get_api_read_session_with_depends() -> AsyncIterator[async_scoped_session[AsyncSession]]:
    """Retrieve an async read session context that self-closes.

    Yields:
        session (async_scoped_session): An asynchronous `read` scoped session

    """
    session = async_scoped_session(
        session_factory=get_db_session(_engine_api_read, 'read'),
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
        session_factory=get_db_session(_engine_read, 'read'),
        scopefunc=current_task,
    )
    try:
        yield session
    finally:
        await session.close()


@asynccontextmanager
async def get_api_read_session_with_context() -> AsyncIterator[async_scoped_session[AsyncSession]]:
    """Retrieve an async read session context that self-closes. This should be used when NOT using FastAPI's Depends.

    Yields:
        session (async_scoped_session): An asynchronous `read` scoped session

    """
    session = async_scoped_session(
        session_factory=get_db_session(_engine_api_read, 'read'),
        scopefunc=current_task,
    )
    try:
        yield session
    finally:
        await session.close()


# I believe @asynccontextmanager is not needed here as long as we are using it as a dependency with Depends
# https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/
async def get_write_session_with_depends() -> AsyncIterator[async_scoped_session[AsyncSession]]:
    """Retrieve an async write session context that self-closes. This should be used when using FastAPI's Depends.

    Yields:
        session (async_scoped_session): An asynchronous `write` scoped session

    """
    session = async_scoped_session(
        session_factory=get_db_session(_engine_write, 'write'),
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
        session_factory=get_db_session(_engine_write, 'write'),
        scopefunc=current_task,
    )
    try:
        yield session
    finally:
        await session.close()
