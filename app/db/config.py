from sqlmodel import create_engine

import app.db.models  # noqa: F401
from app.core.config import get_settings

settings = get_settings()
engine = create_engine(str(settings.DATABASE_URL))
