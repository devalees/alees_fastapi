import pytest
from httpx import AsyncClient

@pytest.mark.api
async def test_healthz_live_returns_200_with_alive_status(test_client: AsyncClient):
    """
    Test that the /healthz/live endpoint returns:
    - HTTP status code 200
    - JSON response with {"status": "alive"}
    """
    # Arrange
    # (No specific arrangement needed for the liveness check)
    
    # Act
    response = await test_client.get("/api/v1/healthz/live")
    
    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "alive"} 