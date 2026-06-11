from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from .jwt import get_jwt_instance
from .users import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> dict[str, str]:
    """
    Endpoint to obtain a JWT access token for the given user, if the credentials are valid.
    """

    user = authenticate_user(
        form_data.username, form_data.password
    )  # username can be email

    data = {
        "email": user.email,
        "user_id": user.user_id,
        "full_name": user.full_name,
    }

    token = get_jwt_instance().create_access_token(user.email, data)

    return {"access_token": token, "token_type": "bearer"}
