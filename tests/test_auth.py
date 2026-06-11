from fastapi.testclient import TestClient

from app.core.config import get_settings

settings = get_settings()


def test_login_success(client: TestClient) -> None:
    """Test successful login with valid credentials"""
    login_data = {"username": "user@example.com", "password": "123456"}

    response = client.post(
        f"{settings.API_PREFIX}/auth/token",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200


def test_login_invalid_email(client: TestClient) -> None:
    """Test login with invalid email"""
    login_data = {"username": "nonexistent@example.com", "password": "123456"}

    response = client.post(
        f"{settings.API_PREFIX}/auth/token",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 401
    assert "Invalid credentials" in response.json().get("detail", "")


def test_login_invalid_password(client: TestClient) -> None:
    """Test login with invalid password"""
    login_data = {"username": "user@example.com", "password": "wrongpassword"}

    response = client.post(
        f"{settings.API_PREFIX}/auth/token",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 401


def test_login_missing_username(client: TestClient) -> None:
    """Test login with missing username"""
    login_data = {"password": "123456"}

    response = client.post(
        f"{settings.API_PREFIX}/auth/token",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 422


def test_login_missing_password(client: TestClient) -> None:
    """Test login with missing password"""
    login_data = {"username": "user@example.com"}

    response = client.post(
        f"{settings.API_PREFIX}/auth/token",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 422


def test_login_via_json(client: TestClient) -> None:
    """Test login with JSON payload (should fail)"""
    login_data = {"username": "user@example.com", "password": "123456"}

    response = client.post(
        f"{settings.API_PREFIX}/auth/token",
        json=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 422
