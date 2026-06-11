from dataclasses import dataclass


@dataclass(slots=True)
class RagHit:
    point_id: str
    building_id: str
    building_name: str
    source_url: str | None
    chunk_index: int
    text: str
    score: float
