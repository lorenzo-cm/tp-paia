from fastapi.testclient import TestClient
from httpx import Response

from app.core.config import get_settings

settings = get_settings()


def test_health_endpoint(client: TestClient) -> None:
    response: Response = client.get(f"{settings.API_PREFIX}/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "Health Check: v1"}


def test_protected_endpoint_auth(client: TestClient) -> None:
    login_data = {"username": "user@example.com", "password": "123456"}

    login_response = client.post(
        f"{settings.API_PREFIX}/auth/token",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert login_response.status_code == 200

    token: str = login_response.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    response: Response = client.get(
        f"{settings.API_PREFIX}/v1/protected/example", headers=headers
    )
    assert response.status_code == 200
