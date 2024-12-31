import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.db_init import (
    close_db,
    create_read_engine,
    create_write_engine,
    get_write_session_with_context,
)
from app.db.models import Template


@pytest.fixture(scope='session')
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope='session')
async def setup_test_db(event_loop):
    """Initialize and teardown the test database."""
    await create_read_engine()
    await create_write_engine()
    yield
    await close_db()


@pytest_asyncio.fixture
async def test_session(setup_test_db):
    """Provide a scoped session for tests using the write context manager."""
    async with get_write_session_with_context() as session:
         yield session


@pytest.mark.asyncio
async def test_create_template(test_session: AsyncSession) -> None:
    """Test the creation of a template in the database."""
    template = Template(name='Test Template 1')
    test_session.add(template)
    await test_session.commit()

    results = await test_session.scalars(select(Template))
    templates = list(results)

    assert len(templates) == 1
    assert templates[0].name == 'Test Template 1'


@pytest.mark.asyncio
async def test_template_isolation(test_session: AsyncSession) -> None:
    """Test that templates are properly isolated between tests."""
    results = await test_session.scalars(select(Template))
    templates = list(results)

    # Should be empty due to rollback in fixture
    assert len(templates) == 0
