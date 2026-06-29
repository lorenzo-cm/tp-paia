import json

from sqlalchemy import text
from sqlmodel import Session

from scripts import seed_buildings as seed_module


def test_default_dataset_has_three_distinct_profiles() -> None:
    dataset = seed_module.DEFAULT_DATASET

    assert len(dataset) == 3
    assert dataset[0]["name"] == "Residencial Aurora"
    assert len(dataset[0]["photos_url"]) == 3
    assert dataset[0]["videos_url"] == []
    assert dataset[0]["documents_url"] == []

    assert dataset[1]["name"] == "Casa Mirante das Palmeiras"
    assert len(dataset[1]["photos_url"]) == 1
    assert len(dataset[1]["videos_url"]) == 1
    assert dataset[1]["documents_url"] == []

    assert dataset[2]["name"] == "Brisa do Mar Residence"
    assert len(dataset[2]["photos_url"]) == 1
    assert dataset[2]["videos_url"] == []
    assert len(dataset[2]["documents_url"]) == 1


def test_seed_buildings_upsert_and_index_now(db_engine, monkeypatch, capsys) -> None:
    with Session(db_engine) as db:
        db.exec(text("TRUNCATE buildings RESTART IDENTITY CASCADE"))  # type: ignore[call-overload]
        db.commit()
    monkeypatch.setattr(seed_module, "engine", db_engine)
    monkeypatch.setattr(
        "app.db.config.engine",
        db_engine,
    )
    monkeypatch.setattr(
        seed_module,
        "DEFAULT_DATASET",
        [
            {
                "name": "Residencial Aurora",
                "information": "Lazer completo.",
                "photos_url": [],
                "videos_url": [],
                "documents_url": [],
                "source_url": "https://example.com/aurora",
                "extraction_version": "seed-v1",
            }
        ],
    )
    monkeypatch.setattr("sys.argv", ["seed_buildings.py", "--upsert", "--index-now"])

    seed_module.main()
    seed_module.main()

    captured = capsys.readouterr().out.strip().splitlines()
    first = json.loads(captured[0])
    second = json.loads(captured[1])
    assert first["created"] == 1
    assert second["updated"] == 1
