"""Fixtures and setup to test the app."""

from typing import Callable, Generator
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.db_init import get_write_session_with_depends
from app.db.models import Template
from app.main import app
from app.providers.provider_aws import ProviderAWS


@pytest.fixture(scope='session')
def client() -> TestClient:
    """Return a test client.

    Returns
    -------
        TestClient: A test client to test with

    """
    test_client = TestClient(app)
    test_client.app.state.providers = {'aws': Mock(spec=ProviderAWS)}
    return test_client


@pytest.fixture(scope='session')
def db_session() -> AsyncSession:
    """Create a database session fixture for testing.

    Returns
    -------
    AsyncSession
        An async SQLAlchemy session for database operations.

    """
    return get_write_session_with_depends()


@pytest.fixture
def sample_template(db_session: AsyncSession) -> Generator[Callable[[str], Template], None, None]:
    """Create a fixture for generating test template instances.

    Parameters
    ----------
    db_session : AsyncSession
        The database session used for database operations.

    Yields
    ------
    Callable[[str], Template]
        A function that takes a template name and returns a new Template instance.

    """
    template_ids: list[str] = ['d5b6e67c-8e2a-11ee-8b8e-0242ac120002']

    def _sample_template(name: str) -> Template:
        """Create and persist a new template instance.

        Args:
        ----
        name : str
            The name for the new template.

        Returns:
        -------
        Template
            The newly created template instance.

        """
        template = Template(name=name)
        db_session.add(template)
        db_session.commit()
        template_ids.append(template.id)
        return template

    yield _sample_template

    stmt = delete(Template).where(Template.id.in_(template_ids))
    db_session.execute(stmt)
    db_session.commit()
