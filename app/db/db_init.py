"""Set up the database engine and session for the application."""

from asyncio import current_task
from typing import AsyncIterator

from fastapi.concurrency import asynccontextmanager
from loguru import logger
from sqlalchemy import MetaData
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)

from app.db import ENP_DB_READ_URI, ENP_DB_WRITE_URI, NAPI_DB_READ_URI, NAPI_DB_WRITE_URI
from app.db.base import Base

_engine_enp_read: AsyncEngine
_engine_enp_write: AsyncEngine
_engine_napi_read: AsyncEngine
_engine_napi_write: AsyncEngine
metadata_legacy: MetaData


async def init_db() -> None:
    """Initialize the database engine."""
    logger.info('Initializing the database engines...')

    # Without this import, Base.metatable (used below) will not point to any tables, and the
    # call to "run_sync" will not create anything.
    import app.db.models  # noqa

    # These methods are copy/paste due to globals.
    await create_write_engine()
    await create_read_engine()

    # notification_api database connections
    await init_napi_metadata()

    logger.info('...database engines initialized.')


async def create_write_engine() -> None:
    """Create the async write engine."""
    global _engine_enp_write, _engine_napi_write
    # Create the write database engine.
    # echo=True logs the queries that are executed.  Set it to False to disable these logs.
    _engine_enp_write = create_async_engine(ENP_DB_WRITE_URI, echo=False)
    async with _engine_enp_write.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
        except IntegrityError:  # pragma: no cover
            # Async workers on a fresh container will try to create tables at the same time - No deployed impact
            pass
    # Connect to the notification_api database
    _engine_napi_write = create_async_engine(NAPI_DB_WRITE_URI, echo=False)


async def create_read_engine() -> None:
    """Create the async read engine."""
    global _engine_enp_read, _engine_napi_read
    # Create the read database engine.
    # echo=True logs the queries that are executed.  Set it to False to disable these logs.
    _engine_enp_read = create_async_engine(ENP_DB_READ_URI, echo=False)
    async with _engine_enp_read.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
        except IntegrityError:  # pragma: no cover
            # Async workers on a fresh container will try to create tables at the same time - No deployed impact
            pass
    # Connect to the notification_api database
    _engine_napi_read = create_async_engine(NAPI_DB_READ_URI, echo=False)


async def init_napi_metadata() -> None:
    """Initialize the API database engine."""
    global metadata_legacy

    metadata_legacy = MetaData()
    async with _engine_napi_read.connect() as conn:
        # Reflect the api tables, using the api read engine, and ApiBase.
        await conn.run_sync(metadata_legacy.reflect)


async def close_db() -> None:
    """Close the database engines."""
    if _engine_enp_read is not None:
        await _engine_enp_read.dispose()

    if _engine_enp_write is not None:
        await _engine_enp_write.dispose()

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
async def get_read_session_with_depends(enp: bool = True) -> AsyncIterator[async_scoped_session[AsyncSession]]:
    """Retrieve an async read session context that self-closes.

    Args:
        enp (bool): True for enp otherwise notification-api

    Yields:
        session (async_scoped_session): An asynchronous `read` scoped session

    """
    session = async_scoped_session(
        session_factory=get_db_session(_engine_enp_read if enp else _engine_napi_read, 'read'),
        scopefunc=current_task,
    )
    try:
        yield session
    finally:
        await session.close()


@asynccontextmanager
async def get_read_session_with_context(enp: bool = True) -> AsyncIterator[async_scoped_session[AsyncSession]]:
    """Retrieve an async read session context that self-closes. This should be used when NOT using FastAPI's Depends.

    Args:
        enp (bool): True for enp otherwise notification-api

    Yields:
        session (async_scoped_session): An asynchronous `read` scoped session

    """
    session = async_scoped_session(
        session_factory=get_db_session(_engine_enp_read if enp else _engine_napi_read, 'read'),
        scopefunc=current_task,
    )
    try:
        yield session
    finally:
        await session.close()


# I believe @asynccontextmanager is not needed here as long as we are using it as a dependency with Depends
# https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/
async def get_write_session_with_depends(enp: bool = True) -> AsyncIterator[async_scoped_session[AsyncSession]]:
    """Retrieve an async write session context that self-closes. This should be used when using FastAPI's Depends.

    Args:
        enp (bool): True for enp otherwise notification-api

    Yields:
        session (async_scoped_session): An asynchronous `write` scoped session

    """
    session = async_scoped_session(
        session_factory=get_db_session(_engine_enp_write if enp else _engine_napi_write, 'write'),
        scopefunc=current_task,
    )
    try:
        yield session
    finally:
        await session.close()


@asynccontextmanager
async def get_write_session_with_context(enp: bool = True) -> AsyncIterator[async_scoped_session[AsyncSession]]:
    """Retrieve an async write session context that self-closes.

    Args:
        enp (bool): True for enp otherwise notification-api

    Yields:
        session (async_scoped_session): An asynchronous `write` scoped session

    """
    session = async_scoped_session(
        session_factory=get_db_session(_engine_enp_write if enp else _engine_napi_write, 'write'),
        scopefunc=current_task,
    )
    try:
        yield session
    finally:
        await session.close()
