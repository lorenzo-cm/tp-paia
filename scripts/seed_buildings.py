from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlmodel import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.config import engine
from app.db.models import BuildingCreate, BuildingUpdate
from app.db.repositories import BuildingRepository
from app.services.catalog_admin import CatalogAdminService
from app.services.real_estate_rag.factory import get_building_rag_service
from app.core.config import get_settings

DEFAULT_DATASET = [
    {
        "name": "Residencial Aurora",
        "information": "Apartamentos de 2 e 3 quartos, lazer completo e localizacao central.",
        "photos_url": [
            "https://cdn.example.com/aurora/fachada-01.jpg",
            "https://cdn.example.com/aurora/lazer-piscina.jpg",
        ],
        "videos_url": ["https://cdn.example.com/aurora/tour.mp4"],
        "documents_url": ["https://cdn.example.com/aurora/memorial.pdf"],
        "source_url": "https://example.com/aurora",
        "extraction_version": "seed-v1",
    },
    {
        "name": "Mirante das Palmeiras",
        "information": "Unidades compactas com varanda, coworking e facil acesso ao metro.",
        "photos_url": ["https://cdn.example.com/mirante/fachada.jpg"],
        "videos_url": ["https://cdn.example.com/mirante/apresentacao.mp4"],
        "documents_url": ["https://cdn.example.com/mirante/book.pdf"],
        "source_url": "https://example.com/mirante",
        "extraction_version": "seed-v1",
    },
]


def _load_items(path: str | None) -> list[dict]:
    if path is None:
        return DEFAULT_DATASET
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _quote_identifier(identifier: str) -> str:
    return identifier.replace('"', '""')


def ensure_database_exists(database_url: str) -> None:
    url = make_url(database_url)
    database_name = url.database
    if not database_name:
        raise ValueError("DATABASE_URL does not include a database name")

    bootstrap_url = url.set(database="postgres")
    bootstrap_engine = create_engine(bootstrap_url, isolation_level="AUTOCOMMIT")
    try:
        with bootstrap_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
                {"database_name": database_name},
            ).scalar_one_or_none()
            if exists is None:
                conn.exec_driver_sql(f'CREATE DATABASE "{_quote_identifier(database_name)}"')
    finally:
        bootstrap_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed buildings catalog")
    parser.add_argument("--input", help="Path to a JSON file with a list of buildings")
    parser.add_argument("--upsert", action="store_true", help="Update by source_url when possible")
    parser.add_argument("--index-now", action="store_true", help="Trigger reindex after persistence")
    args = parser.parse_args()

    items = _load_items(args.input)
    ensure_database_exists(str(get_settings().DATABASE_URL))
    with Session(engine) as db:
        repo = BuildingRepository(db)
        service = CatalogAdminService.from_session(db, get_building_rag_service())
        created = 0
        updated = 0
        for raw in items:
            source_url = raw.get("source_url")
            if args.upsert and source_url:
                current = repo.get_by_source_url(source_url)
            else:
                current = None
            if current is None:
                service.create_building(BuildingCreate(**raw))
                created += 1
                continue
            repo.update(BuildingUpdate(id=current.id, **raw))
            updated += 1
        db.commit()

        if args.index_now:
            summary = service.reindex_all()
            print(json.dumps({"created": created, "updated": updated, "indexed": summary.requested}))
            return
        print(json.dumps({"created": created, "updated": updated}))


if __name__ == "__main__":
    main()
