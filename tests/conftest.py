"""Fixtures and setup to test the app."""

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Callable
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import UUID4

from app.auth import JWTPayloadDict
from app.constants import NotificationType
from app.main import CustomFastAPI, app
from app.providers.provider_aws import ProviderAWS
from app.state import ENPState

ADMIN_SECRET_KEY = os.getenv('ENP_ADMIN_SECRET_KEY', 'not-very-secret')
ALGORITHM = os.getenv('ENP_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv('ENP_ACCESS_TOKEN_EXPIRE_SECONDS', 60))


@pytest.fixture(autouse=True)
async def init_database():
    # Need to reflect after the pytest async loop is running
    from app.db.db_init import _initialzied, init_db

    if not _initialzied:
        await init_db()


class ENPTestClient(TestClient):
    """An ENP test client for the CustomFastAPI app.

    Args:
        TestClient (TestClient): FastAPI's test client.
    """

    app: CustomFastAPI
    token_expiry = 60
    client_id = 'test'
    client_secret = 'not-very-secret'

    def __init__(self, app: CustomFastAPI) -> None:
        """Initialize the ENPTestClient.

        Args:
            app (CustomFastAPI): The FastAPI application instance.
        """
        headers = {
            'Authorization': f'Bearer {generate_token()}',
        }
        super().__init__(app, headers=headers)


@pytest.fixture(scope='session')
def client() -> ENPTestClient:
    """Return a test client.

    Returns:
        ENPTestClient: A test client to test with

    """
    app.enp_state = ENPState()

    app.enp_state.providers['aws'] = Mock(spec=ProviderAWS)

    return ENPTestClient(app)


def generate_token(sig_key: str = ADMIN_SECRET_KEY, payload: JWTPayloadDict | None = None) -> str:
    """Generate a JWT token.

    Args:
        sig_key (str): The key to sign the JWT token with.
        payload (JWTPayloadDict): The payload to include in the JWT token.

    Returns:
        str: The signed JWT token.
    """
    headers = {
        'typ': 'JWT',
        'alg': ALGORITHM,
    }
    if payload is None:
        payload = JWTPayloadDict(
            iss='enp',
            iat=int(time.time()),
            exp=int(time.time()) + ACCESS_TOKEN_EXPIRE_SECONDS,
        )
    return jwt.encode(dict(payload), sig_key, headers=headers)


@pytest.fixture
def mock_template() -> Callable[..., AsyncMock]:
    """Return a Callable that returns a mock of a template that would be returned from the notification api db."""

    def _create_mock_template(
        id: UUID4 = uuid4(),
        name: str = 'test_template',
        template_type: NotificationType = NotificationType.SMS,
        created_at: datetime = datetime.now(timezone.utc),
        updated_at: datetime = datetime.now(timezone.utc),
        content: str = 'test content',
        service_id: UUID4 = uuid4(),
        subject: str = 'test subject',
        created_by_id: UUID4 = uuid4(),
        version: int = 1,
        archived: bool = False,
        process_type: str = 'p_type',
        hidden: bool = False,
        provider_id: UUID4 = uuid4(),
        communication_item_id: UUID4 = uuid4(),
        reply_to_email_address: str = 'test@mail.com',
        onsite_notification: bool = False,
        content_as_html: str = '<html><body>test content as html</body></html>',
        content_as_plain_text: str = 'test content as plain text',
    ) -> AsyncMock:
        """Return a mock template."""
        mock_template = AsyncMock()
        mock_template.id = id
        mock_template.name = name
        mock_template.template_type = template_type
        mock_template.created_at = created_at
        mock_template.updated_at = updated_at
        mock_template.content = content
        mock_template.service_id = service_id
        mock_template.subject = subject
        mock_template.created_by_id = created_by_id
        mock_template.version = version
        mock_template.archived = archived
        mock_template.process_type = process_type
        mock_template.hidden = hidden
        mock_template.provider_id = provider_id
        mock_template.communication_item_id = communication_item_id
        mock_template.reply_to_email_address = reply_to_email_address
        mock_template.onsite_notification = onsite_notification
        mock_template.content_as_html = content_as_html
        mock_template.content_as_plain_text = content_as_plain_text

        return mock_template

    return _create_mock_template


def pytest_sessionfinish(session, exitstatus):
    asyncio.run(_clean_table_data())


async def _clean_table_data():
    from sqlalchemy import select, text

    from app.db.db_init import get_write_session_with_context, init_db, metadata_legacy

    # Reflect the metadata, prep write session
    await init_db()

    print()

    color = '\033[91m'
    reset = '\033[0m'
    TRUNCATE_ARTIFACTS = os.getenv('TRUNCATE_ARTIFACTS', 'False') == 'True'

    skip_tables = (
        'alembic_version',
        'auth_type',
        'branding_type',
        'dm_datetime',
        'key_types',
        'notification_status_types',
        'template_process_type',
        'provider_details',
        'provider_details_history',
    )

    acceptable_counts = {
        'communication_items': 4,
        'job_status': 9,
        'key_types': 3,
        # 'provider_details': 9,  # TODO: 1631
        # 'provider_details_history': 9,  # TODO: 1631
        'provider_rates': 5,
        # 'rates': 2,
        'service_callback_channel': 2,
        'service_callback_type': 3,
        'service_permission_types': 12,
    }
    tables_with_artifacts = []
    artifact_counts = []

    # Use metadata to query the table and add the table name to the list if there are any records
    async with get_write_session_with_context() as session:
        for _, v in metadata_legacy.tables.items():
            if v.name not in skip_tables:
                row_count = len((await session.execute(select(metadata_legacy.tables[v.name]))).all())

                if v.name in acceptable_counts and row_count <= acceptable_counts[v.name]:
                    continue
                elif row_count > 0:
                    artifact_counts.append((row_count))
                    tables_with_artifacts.append(v.name)
                    session.exitstatus = 1

        if tables_with_artifacts and TRUNCATE_ARTIFACTS:
            print('\n')
            for i, table in enumerate(tables_with_artifacts):
                # Skip tables that may have necessary information
                if table not in acceptable_counts:
                    session.execute(text(f"""TRUNCATE TABLE {table} CASCADE"""))
                    print(f'Truncating {color}{table}{reset} with cascade...{artifact_counts[i]} records removed')
                else:
                    print(f'Table {table} contains too many records but {color}cannot be truncated{reset}.')
            session.commit()
            print(f'\n\nThese tables contained artifacts: {tables_with_artifacts}\n\n{color}UNIT TESTS FAILED{reset}')
        elif tables_with_artifacts:
            print(f'\n\nThese tables contain artifacts: {color}{tables_with_artifacts}\n\nUNIT TESTS FAILED{reset}')
        else:
            color = '\033[32m'  # Green - pulled out for clarity
            print(f'\n\n{color}DATABASE IS CLEAN{reset}')
