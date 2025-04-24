"""Test any implemented samples."""


async def test_sample_user(sample_user) -> None:
    await sample_user()


async def test_two(sample_service) -> None:
    await sample_service()
