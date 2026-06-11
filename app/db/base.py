from sqlmodel import SQLModel

import app.db.models  # noqa: F401  # register all tables on SQLModel.metadata

metadata = SQLModel.metadata
