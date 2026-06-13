from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlmodel import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.config import engine
from app.services.catalog_admin import CatalogAdminService
from app.services.real_estate_rag.factory import get_building_rag_service


def main() -> None:
    with Session(engine) as db:
        service = CatalogAdminService.from_session(db, get_building_rag_service())
        summary = service.reindex_all()
        print(json.dumps({"requested": summary.requested, "building_ids": summary.building_ids}))


if __name__ == "__main__":
    main()
