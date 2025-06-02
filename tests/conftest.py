"""Fixtures and setup to test the app."""

import asyncio
import os
import time
import tomllib
from typing import Any
from unittest.mock import Mock

import jwt
import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import UUID4
from sqlalchemy import TextClause, select, text
from starlette_context import plugins
from starlette_context.middleware import ContextMiddleware

from app.auth import JWTPayloadDict
from app.db.db_init import get_read_session_with_context, get_write_session_with_context, init_db, metadata_legacy
from app.main import CustomFastAPI, app
from app.providers.provider_aws import ProviderAWS
from app.routers import LegacyTimedAPIRoute
from app.state import ENPState

ADMIN_SECRET_KEY = os.getenv('ENP_ADMIN_SECRET_KEY', 'not-very-secret')
ALGORITHM = os.getenv('ENP_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv('ENP_ACCESS_TOKEN_EXPIRE_SECONDS', 60))

# pytest cleanup script values
_COLOR_GREEN = '\033[32m'
_COLOR_RED = '\033[91m'
_COLOR_RESET = '\033[0m'
_DELETE_DB_ARTIFACTS = True  # os.getenv('DELETE_DB_ARTIFACTS', 'False') == 'True'

router = APIRouter(prefix='/test', route_class=LegacyTimedAPIRoute)


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
    app.include_router(router)

    app.enp_state.providers['aws'] = Mock(spec=ProviderAWS)

    app.add_middleware(
        ContextMiddleware,
        plugins=(plugins.RequestIdPlugin(force_new_uuid=False),),
    )
    return ENPTestClient(app)


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
        issuer (str): Token issuer
        algorithm (str): Algorithm to encode with
        iat: (int): Issued at time
        exp: (int): Expires at time

    Returns:
        dict[str, str]: Headers for an authorized request
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


with open('tests/napi_table_data.toml', 'rb') as f:
    _napi_toml_table_data = tomllib.load(f)

_napi_table_data: dict[str, dict[str, str | list[str | UUID4]]] = _napi_toml_table_data['napi_table_data']
_skip_tables: list[str] = _napi_toml_table_data['skip_tables']['table_names']


# No need to cover the test cleanup with a test
def pytest_sessionfinish(
    session: pytest.Session,
    exitstatus: int | pytest.ExitCode,
) -> None:  # pragma: no cover
    """Ran after all tests.

        The flow is:
            1. Gather all table names
            2. Skip tables that do not need to be checked
            3. Check pre-defined tables that are listed in napi_table_data.toml
            4. Catch any tables that have extra data so they can be cleaned
            5. Clean all unexpected data

    Args:
        session (Any): The pytest session, not DB related
        exitstatus (Any): Unknown but mandatory
    """
    asyncio.run(_validate_and_clean_tables(session))


async def _validate_and_clean_tables(pt_session: pytest.Session) -> None:  # pragma: no cover
    """Validate and clean tables.

        See pytest_session_finish for overview.

    Args:
        pt_session (pytest.Session): Pytest Session object, used for setting exit status
    """
    # Reflect the metadata, prep write session
    await init_db()

    tables_with_artifacts: list[str] = []
    artifact_counts: list[int] = []

    for table in metadata_legacy.tables.values():
        if table.name in _skip_tables:
            continue
        elif table.name in _napi_table_data:
            await _check_table(table.name, artifact_counts, tables_with_artifacts, pt_session)
        else:
            # Make sure this table is empty, so we do not accidentally add any artifacts.
            async with get_read_session_with_context() as session:
                rows_count = len((await session.execute(select(metadata_legacy.tables[table.name]))).all())
            if rows_count != 0:
                artifact_counts.append(rows_count)
                tables_with_artifacts.append(table.name)
                print(f'Table is not in the config and is leaving artifacts: {table.name} - Ensure proper teardown')
                pt_session.exitstatus = 1
                # Add this to table data so we can keep the code simple in the cleanup
                _napi_table_data[table.name] = {}
                _napi_table_data[table.name]['key'] = ''
                _napi_table_data[table.name]['keys'] = []

    await _clean_tables(artifact_counts, tables_with_artifacts)


async def _check_table(
    name: str,
    artifact_counts: list[int],
    tables_with_artifacts: list[str],
    pt_session: pytest.Session,
) -> None:  # pragma: no cover
    async with get_read_session_with_context() as session:
        rows = (await session.execute(select(metadata_legacy.tables[name]))).all()

    key_str = str(_napi_table_data[name]['key'])
    fail_count = 0
    for row in rows:
        # Have to use getattr because this is dynamic and row expects dot notation, but we have a string
        if str(getattr(row, key_str)) in _napi_table_data[name]['keys']:
            continue
        else:
            fail_count += 1
    # Only add to the artifacts if there were any failures
    if fail_count > 0:
        artifact_counts.append((fail_count))
        tables_with_artifacts.append(name)
        pt_session.exitstatus = 1


def _get_table_delete_statement(table: str, where_item: str, ids: list[str | UUID4]) -> TextClause:  # pragma: no cover
    if len(ids) == 0:
        # Earlier in the process this table had extra data that is not tracked.
        stmt = text(f"""DELETE FROM {table};""")
    elif len(ids) == 1:
        # The ORM does not handle (<uuid>,). The extra comma breaks the query, so do a direct delete
        stmt = text(f"""DELETE FROM {table} WHERE  {where_item} != {ids[0]};""")
    else:
        # Postgres doesn't accept ['<uuid>'], has to be in the form, ('<uuid>')
        stmt = text(f"""DELETE FROM {table} WHERE {where_item} not in {tuple(ids)};""")
    return stmt


async def _clear_table(artifact_counts: list[int], tables_with_artifacts: list[str]) -> None:  # pragma: no cover
    async with get_write_session_with_context() as session:
        try:
            for i, table in enumerate(tables_with_artifacts):
                # Would have to load each "table" into a dataclass. This is a cleanup script, ignore the mypy errors here.
                where_item: str = _napi_table_data[table]['key']  # type:ignore
                ids: list[str | UUID4] = _napi_table_data[table]['keys']  # type:ignore
                stmt = _get_table_delete_statement(table, where_item, ids)
                await session.execute(stmt)
                print(
                    f'Deleting extra {_COLOR_RED}{table}{_COLOR_RESET} entries...{artifact_counts[i]} record(s) removed'
                )
            await session.commit()
        except Exception as e:
            print(f'Unable to clear records due to {e}')
        else:
            print(
                f'\n\nThese tables contained artifacts: {tables_with_artifacts}\n\n{_COLOR_RED}UNIT TESTS FAILED{_COLOR_RESET}'
            )


async def _clean_tables(artifact_counts: list[int], tables_with_artifacts: list[str]) -> None:  # pragma: no cover
    """Cleans database tables if the environment variable is set and there are tables to clean.

    Args:
        artifact_counts (list[int]): Parallel list of artifact counts
        tables_with_artifacts (list[str]): Parallel list of tables with artifacts
    """
    if tables_with_artifacts and _DELETE_DB_ARTIFACTS:
        print('\n\n')
        await _clear_table(artifact_counts, tables_with_artifacts)
    elif tables_with_artifacts:
        print(f'\n\nThese tables contain artifacts: {_COLOR_RED}')
        for c, a in zip(artifact_counts, tables_with_artifacts):
            print(f'{c:>4} {a}')
        print(f'\n\nUNIT TESTS FAILED{_COLOR_RESET}')
    else:
        print(f'\n\n{_COLOR_GREEN}DATABASE IS CLEAN{_COLOR_RESET}')
