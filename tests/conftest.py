"""Fixtures and setup to test the app."""

import pytest
from fastapi.testclient import TestClient
from jinja2 import Template
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.db_init import get_write_session
from app.main import app


@pytest.fixture(scope='session')
def client() -> TestClient:
    """Return a test client.

    Returns
    -------
        TestClient: A test client to test with

    """
    return TestClient(app)


@pytest.fixture(scope='session')
def db_session() -> AsyncSession:
    return await get_write_session()


@pytest.fixture
def create_template(db_session):
    template_ids = ['d5b6e67c-8e2a-11ee-8b8e-0242ac120002']

    def _create_template(name: str) -> Template:
        template = Template(name=name)
        db_session.add(template)
        db_session.commit()
        template_ids.append(template.id)
        return template

    yield _create_template

    stmt = delete(Template).where(Template.id._in(template_ids))
    db_session.execute(stmt)
    db_session.commit()
