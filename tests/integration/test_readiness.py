import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_readiness() -> None:
    from app.database import check_database_ready

    assert await check_database_ready() is True
