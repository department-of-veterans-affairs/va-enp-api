"""Set up the database engine and session for the application."""

from asyncio import current_task
from typing import AsyncIterator

from fastapi.concurrency import asynccontextmanager
from loguru import logger
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)

from app.db import NAPI_DB_READ_URI, NAPI_DB_WRITE_URI

_engine_napi_read: AsyncEngine | None = None
_engine_napi_write: AsyncEngine | None = None
_initialzied: bool = False
metadata_legacy: MetaData = MetaData()


async def init_db(pool_pre_ping: bool = False) -> None:
    """Initialize the database engine.

    Args:
        pool_pre_ping (bool): should test for a live db connection before query
    """
    global _initialzied
    logger.info('Initializing the database engines...')

    # These methods are copy/paste due to globals.
    create_engines(pool_pre_ping)

    # notification_api database connections
    await init_napi_metadata()
    _initialzied = True

    logger.info('...database engines initialized.')


def create_engines(pool_pre_ping: bool) -> None:
    """Create the async read and write engines.

    Args:
        pool_pre_ping (bool): should test for a live db connection before query
    """
    global _engine_napi_read, _engine_napi_write
    # Create the read database engine.
    _engine_napi_read = create_async_engine(NAPI_DB_READ_URI, echo=False, pool_pre_ping=pool_pre_ping)
    # Create the write database engine.
    _engine_napi_write = create_async_engine(NAPI_DB_WRITE_URI, echo=False, pool_pre_ping=pool_pre_ping)


async def init_napi_metadata() -> None:
    """Initialize the API database engine."""
    global metadata_legacy

    # Type checking ignored because the global is initially None, but it should never have that value
    # at this point in the code.  mypy complains that None has no "connect" attribute.
    async with _engine_napi_read.connect() as conn:  # type: ignore
        # Reflect the api tables, using the api read engine, and ApiBase.
        await conn.run_sync(metadata_legacy.reflect)


async def close_db() -> None:
    """Close the database engines."""
    if _engine_napi_read is not None:
        await _engine_napi_read.dispose()

    if _engine_napi_write is not None:
        await _engine_napi_write.dispose()


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
        session_factory=get_db_session(_engine_napi_read, 'read'),
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
        session_factory=get_db_session(_engine_napi_read, 'read'),
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
        session_factory=get_db_session(_engine_napi_write, 'write'),
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
        session_factory=get_db_session(_engine_napi_write, 'write'),
        scopefunc=current_task,
    )
    try:
        yield session
    finally:
        await session.close()
