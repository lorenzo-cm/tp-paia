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
        "information": (
            "Apartamento compacto em regiao central, ideal para primeiro imovel, casal "
            "ou investidor que busca praticidade no dia a dia. O empreendimento oferece "
            "unidades de 1 e 2 quartos com plantas entre 48 e 67 metros quadrados, "
            "ambientes bem resolvidos, cozinha integrada e vaga de garagem coberta em "
            "algumas unidades. A localizacao facilita acesso a comercio, servicos, "
            "transporte e vida urbana, enquanto o condominio entrega uma proposta enxuta "
            "e funcional para quem quer morar perto de tudo. As imagens cadastradas "
            "mostram ambientes como cozinha, banheiro e garagem, o que ajuda o atendimento "
            "a detalhar o estilo do imovel de forma objetiva."
        ),
        "photos_url": [
            "https://pub-78d5c1f023a34caab9a8c5564c4931e8.r2.dev/imagem_cozinha.webp",
            "https://pub-78d5c1f023a34caab9a8c5564c4931e8.r2.dev/imagem_banheiro.jpg",
            "https://pub-78d5c1f023a34caab9a8c5564c4931e8.r2.dev/imagem_garagem.jpeg",
        ],
        "videos_url": [],
        "documents_url": [],
        "source_url": "https://example.com/residencial-aurora",
        "extraction_version": "seed-v2",
    },
    {
        "name": "Casa Mirante das Palmeiras",
        "information": (
            "Casa ampla voltada para familias que valorizam espaco, lazer privativo e "
            "conforto para receber convidados. O imovel conta com 4 suites, sala em "
            "dois ambientes, cozinha generosa, varanda gourmet, piscina, quintal e "
            "garagem para varios carros, com area construida aproximada de 320 metros "
            "quadrados. O perfil e de moradia definitiva para quem busca mais area "
            "interna e externa, com destaque para convivio social e rotina familiar. "
            "A foto principal destaca a piscina e o video ajuda o cliente a entender a "
            "escala da casa e a distribuicao dos ambientes."
        ),
        "photos_url": [
            "https://pub-78d5c1f023a34caab9a8c5564c4931e8.r2.dev/imagem_casa_piscina.jpg"
        ],
        "videos_url": [
            "https://pub-78d5c1f023a34caab9a8c5564c4931e8.r2.dev/video_imovel.mp4"
        ],
        "documents_url": [],
        "source_url": "https://example.com/casa-mirante-das-palmeiras",
        "extraction_version": "seed-v2",
    },
    {
        "name": "Brisa do Mar Residence",
        "information": (
            "Imovel com proposta de segunda moradia ou vida leve perto da praia, pensado "
            "para quem prioriza descanso, vista aberta e atmosfera de litoral. O projeto "
            "traz 3 quartos, varanda ampla, integracao entre sala e area externa e "
            "aproximadamente 110 metros quadrados, com foco em ventilacao, iluminacao "
            "natural e experiencia de uso nos fins de semana ou temporadas longas. "
            "O perfil combina bem com clientes que perguntam sobre proximidade da orla, "
            "lazer, praticidade de manutencao e uso para familia ou temporadas. A imagem "
            "de jardim reforca o clima do imovel e o documento em PDF concentra as "
            "especificacoes principais para consulta mais detalhada."
        ),
        "photos_url": [
            "https://pub-78d5c1f023a34caab9a8c5564c4931e8.r2.dev/imagem_jardim.jpg"
        ],
        "videos_url": [],
        "documents_url": [
            "https://pub-78d5c1f023a34caab9a8c5564c4931e8.r2.dev/EspecificacoesImovel.pdf"
        ],
        "source_url": "https://example.com/brisa-do-mar-residence",
        "extraction_version": "seed-v2",
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
