"""."""

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.db import DB_WRITE_URI
from app.db.base import Base

engine = None


async def init_db() -> AsyncEngine:
    """Initialize the database engine.

    Returns
    -------
        AsyncEngine: the db engine

    """
    global engine
    logger.info('Initializing the database session... with uri: {}', DB_WRITE_URI)
    engine = create_async_engine(DB_WRITE_URI, echo=True)

    async with engine.begin() as conn:
        logger.info(f'{Base.metadata.tables=}')
        await conn.run_sync(Base.metadata.create_all)

    return engine

    # for AsyncEngine created in function scope, close and
    # clean-up pooled connections
    await engine.dispose()


def get_db_session() -> async_sessionmaker[AsyncSession]:
    """Initialize the database read instance.

    Returns
    -------
        async_sessionmaker[AsyncSession]: the async session maker

    """
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    return async_session
