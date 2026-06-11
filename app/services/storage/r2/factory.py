from functools import lru_cache

from app.core.config import get_settings
from app.services.storage.r2.service import R2Service


@lru_cache(maxsize=1)
def get_r2_service() -> R2Service:
    settings = get_settings()
    return R2Service(
        r2_endpoint_url=settings.R2_ENDPOINT_URL,
        r2_access_key_id=settings.R2_ACCESS_KEY_ID,
        r2_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        r2_bucket_name=settings.R2_BUCKET_NAME,
        r2_pub_url=settings.R2_PUB_URL,
    )
