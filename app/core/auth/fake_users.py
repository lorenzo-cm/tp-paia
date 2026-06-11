from dataclasses import dataclass


@dataclass
class FakeUser:
    user_id: str
    email: str
    hashed_password: str
    full_name: str


fake_users: dict[str, FakeUser] = {
    "user@example.com": FakeUser(
        user_id="0",
        email="user@example.com",
        hashed_password="$2a$12$dGgyg5D1yB0EBhV73B6sBuU.6/eYNZoOAYu6ym6Aol.kq2pLambRS",  # bcrypt for '123456'
        full_name="John Doe",
    ),
    "user2@example.com": FakeUser(
        user_id="1",
        email="user2@example.com",
        hashed_password="$2a$12$dGgyg5D1yB0EBhV73B6sBuU.6/eYNZoOAYu6ym6Aol.kq2pLambRS",  # bcrypt for '123456'
        full_name="Jane Doe",
    ),
}
