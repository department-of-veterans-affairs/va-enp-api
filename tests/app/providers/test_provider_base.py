"""Test module for app/providers/provider_base.py."""

import pytest

from app.providers.provider_base import ProviderBase


@pytest.mark.asyncio
async def test_not_implemented_virtual_void() -> None:
    """Ensure all methods that may be implmented raise an exception if they are not yet implemented."""

    class TestProviderDerived(ProviderBase): ...

    derived = TestProviderDerived()

    # Test each "virtual void" method
    with pytest.raises(NotImplementedError):
        await derived._process_email_response()
    with pytest.raises(NotImplementedError):
        await derived._process_push_response()
    with pytest.raises(NotImplementedError):
        await derived._process_sms_response()
    with pytest.raises(NotImplementedError):
        await derived._send_email()
    with pytest.raises(NotImplementedError):
        await derived._send_push()
    with pytest.raises(NotImplementedError):
        await derived._send_sms()
