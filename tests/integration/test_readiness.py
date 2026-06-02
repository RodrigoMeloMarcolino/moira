import pytest

from app.database import check_database_ready


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_readiness() -> None:
    assert await check_database_ready() is True
