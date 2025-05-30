"""Fixtures and setup to test the app."""

import asyncio
import os
import time
from typing import Any, Callable
from unittest.mock import AsyncMock, Mock

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette_context import plugins
from starlette_context.middleware import ContextMiddleware

from app.auth import JWTBearer, JWTPayloadDict
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

    def __init__(self, app: CustomFastAPI, token: str | None = None) -> None:
        """Initialize the ENPTestClient with optional custom token.

        If no token is provided, a default one is generated using `generate_token()`.

        Args:
            app (CustomFastAPI): The FastAPI application instance.
            token (str | None, optional): A JWT Bearer token to use for Authorization.
        """
        if token is None:
            token = generate_token()

        headers = {
            'Authorization': f'Bearer {token}',
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

    app.add_middleware(
        ContextMiddleware,
        plugins=(plugins.RequestIdPlugin(force_new_uuid=False),),
    )
    return ENPTestClient(app)


@pytest.fixture(scope='session')
def client_factory() -> Callable[[str], ENPTestClient]:
    """Returns a factory for creating ENPTestClient with a custom token.

    Returns:
        Callable[[str], ENPTestClient]: Factory function accepting a token string.
    """

    def _create_client(token: str) -> ENPTestClient:
        """Create a test client with the given Bearer token.

        Args:
            token (str): The Bearer token to include in the Authorization header.

        Returns:
            ENPTestClient: A configured test client instance.
        """
        app.enp_state = ENPState()
        app.enp_state.providers['aws'] = Mock(spec=ProviderAWS)
        return ENPTestClient(app, token=token)

    return _create_client


def generate_headers(
    sig_key: str,
    issuer: str,
    algorithm: str = ALGORITHM,
    iat: int = -1,
    exp: int = -1,
) -> dict[str, str]:
    """Generate a signed JWT token using the specified signature key, headers, and payload.

    If no headers are provided, defaults to {'typ': 'JWT', 'alg': ALGORITHM}.
    If no payload is provided, generates a default payload with issuer 'enp',
    current issued-at time (iat), and an expiration (exp) set to the configured duration.

    Args:
        sig_key (str): The secret key used to sign the JWT token.
        headers (dict[str, str] | None): Optional JWT headers. Defaults to standard 'typ' and 'alg'.
        payload (JWTPayloadDict | None): Optional JWT payload. Defaults to a standard payload.

    Returns:
        str: The signed JWT token as a string.
    """
    auth_headers = {
        'typ': 'JWT',
        'alg': algorithm,
    }
    payload = JWTPayloadDict(
        iss=issuer,
        iat=int(time.time()) if iat == -1 else iat,
        exp=(int(time.time()) + ACCESS_TOKEN_EXPIRE_SECONDS) if exp == -1 else exp,
    )
    headers: dict[str, str] = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {jwt.encode(dict(payload), sig_key, headers=auth_headers)}',
    }
    return headers


def generate_token(
    sig_key: str = ADMIN_SECRET_KEY,
    headers: dict[str, str] | None = None,
    payload: JWTPayloadDict | None = None,
) -> str:
    """Generate a signed JWT token using the specified signature key, headers, and payload.

    If no headers are provided, defaults to {'typ': 'JWT', 'alg': ALGORITHM}.
    If no payload is provided, generates a default payload with issuer 'enp',
    current issued-at time (iat), and an expiration (exp) set to the configured duration.

    Args:
        sig_key (str): The secret key used to sign the JWT token.
        headers (dict[str, str] | None): Optional JWT headers. Defaults to standard 'typ' and 'alg'.
        payload (JWTPayloadDict | None): Optional JWT payload. Defaults to a standard payload.

    Returns:
        str: The signed JWT token as a string.
    """
    if headers is None:
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


def generate_token_with_partial_payload(
    sig_key: str,
    payload: dict[str, Any],
) -> str:
    """Generate a JWT token with incomplete payload for testing.

    Args:
        sig_key (str): The key to sign the JWT token with.
        payload (dict): The payload to include in the JWT token.

    Returns:
        str: The signed JWT token.
    """
    headers = {
        'typ': 'JWT',
        'alg': ALGORITHM,
    }
    return jwt.encode(payload, sig_key, headers=headers)


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
