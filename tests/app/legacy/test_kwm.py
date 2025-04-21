async def test_one(sample_user, sample_service):
    # Need to reflect after the pytest async loop is running
    from app.db.db_init import init_db

    await init_db()
    user = await sample_user()
    service = await sample_service(created_by_id=user.id)
    print()
    print(f'one - {service.created_by_id=}')
    print(f'one - {user.id=}')


async def test_two(sample_user, sample_service):
    user = await sample_user()
    service = await sample_service(created_by_id=user.id)
    print()
    print(f'two - {service.created_by_id=}')
    print(f'two - {user.id=}')
