"""Fixtures and setup to test the app."""

import asyncio
import os
import time
from unittest.mock import Mock

import jwt
import pytest
from fastapi.testclient import TestClient

from app.auth import JWTPayloadDict
from app.main import CustomFastAPI, app
from app.providers.provider_aws import ProviderAWS
from app.state import ENPState

ADMIN_SECRET_KEY = os.getenv('ENP_ADMIN_SECRET_KEY', 'not-very-secret')
ALGORITHM = os.getenv('ENP_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv('ENP_ACCESS_TOKEN_EXPIRE_SECONDS', 60))

# pytest cleanup script values
_COLOR_GREEN = '\033[32m'
_COLOR_RED = '\033[91m'
_COLOR_RESET = '\033[0m'
_TRUNCATE_ARTIFACTS = os.getenv('TRUNCATE_ARTIFACTS', 'False') == 'True'


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


_skip_tables = (
    'alembic_version',
    'auth_type',
    'branding_type',
    'dm_datetime',
    'key_types',
    'notification_status_types',
    'template_process_type',
    'provider_details',
    'provider_details_history',
    'organisation_types',
    'invite_status_type',
    'job_status',
)

_acceptable_counts = {
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


# No need to cover the test cleanup with a test
def pytest_sessionfinish(
    session: pytest.Session,
    exitstatus: int | pytest.ExitCode,
) -> None:  # pragma: no cover
    """Ran after all tests.

    Args:
        session (Any): The pytest session, not DB related
        exitstatus (Any): Unknown but mandatory
    """
    asyncio.run(_validate_and_clean_tables(session))


async def _validate_and_clean_tables(pt_session: pytest.Session) -> None:  # pragma: no cover
    """Validate and clean tables.

    Args:
        pt_session (pytest.Session): Pytest Session object, used for setting exit status
    """
    from sqlalchemy import select

    from app.db.db_init import get_read_session_with_context, init_db, metadata_legacy

    # Reflect the metadata, prep write session
    await init_db()

    tables_with_artifacts = []
    artifact_counts = []

    # Use metadata to query the table and add the table name to the list if there are any records
    async with get_read_session_with_context() as session:
        for table in metadata_legacy.tables.values():
            if table.name not in _skip_tables:
                row_count = len((await session.execute(select(metadata_legacy.tables[table.name]))).all())

                if table.name in _acceptable_counts and row_count <= _acceptable_counts[table.name]:
                    continue
                elif row_count > 0:
                    artifact_counts.append((row_count))
                    tables_with_artifacts.append(table.name)
                    pt_session.exitstatus = 1

    await clean_tables(artifact_counts, tables_with_artifacts)


async def clean_tables(artifact_counts: list[int], tables_with_artifacts: list[str]) -> None:  # pragma: no cover
    """Cleans database tables if the environment variable is set and there are tables to clean.

    Args:
        artifact_counts (list[int]): Parallel list of artifact counts
        tables_with_artifacts (list[str]): Parallel list of tables with artifacts
    """
    from sqlalchemy import text

    from app.db.db_init import get_write_session_with_context

    if tables_with_artifacts and _TRUNCATE_ARTIFACTS:
        print('\n\n')
        async with get_write_session_with_context() as session:
            for i, table in enumerate(tables_with_artifacts):
                # Skip tables that may have necessary information
                if table not in _acceptable_counts:
                    await session.execute(text(f"""TRUNCATE TABLE {table} CASCADE"""))
                    print(
                        f'Truncating {_COLOR_RED}{table}{_COLOR_RESET} with cascade...{artifact_counts[i]} records removed'
                    )
                else:
                    print(f'Table {table} contains too many records but {_COLOR_RED}cannot be truncated{_COLOR_RESET}.')
            await session.commit()
            print(
                f'\n\nThese tables contained artifacts: {tables_with_artifacts}\n\n{_COLOR_RED}UNIT TESTS FAILED{_COLOR_RESET}'
            )
    elif tables_with_artifacts:
        print(
            f'\n\nThese tables contain artifacts: {_COLOR_RED}{tables_with_artifacts}\n\nUNIT TESTS FAILED{_COLOR_RESET}'
        )
    else:
        print(f'\n\n{_COLOR_GREEN}DATABASE IS CLEAN{_COLOR_RESET}')
