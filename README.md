# FastAPI Template

Template for fastapi backend development.

This repository uses **uv** for package management, since it is faster and more efficient than `pip` and `setup.py`.


## Features:

- 🚀 **FastAPI** - Framework web moderno e rápido
- 🦄 **Uvicorn** - High performance ASGI server
- 🔒 **JWT Authentication** - Complete authentication system with JWT tokens
- 🧪 **Tests with Pytest** - Complete suite of unit tests and integration tests
- 🎨 **Automatic formatting with Ruff** - Consistent code formatting
- 🔍 **MyPy** - Static type checking for greater robustness
- 📊 **Coverage** - Test coverage reports
- ⚙️ **Centralized configuration** - Configuration management with Pydantic Settings
- 🛡️ **Exception handling** - Robust error handling system
- 📝 **Structured logging** - Configurable logging system
- 💾 **Database** - PostgreSQL with SQLModel
- 🔎 **RAG imobiliário** - Indexação do catálogo com busca híbrida semântica + BM25
- ⚙️ **Worker assíncrono** - Reindexação via Celery/Redis

## First steps

To install the dependencies and create the virtual environment all set up:

```sh
uv sync
```

To run the application:

```sh
uv run python -m scripts.run
```

or using the script:

```sh
bash ./scripts/run.sh
```

## Download new dependencies

To add a new dependency to the project:

```sh
uv add <package>
```

It will automatically update the `uv.lock` file and the `pyproject.toml` file.

## Run tests

To run the tests:

```sh
bash ./scripts/test.sh
```

Faster alternative without coverage:

```sh
uv run pytest
```

## Code formatting and linting

This project uses **Ruff** for code formatting and linting.

It also uses **MyPy** for type checking.

To run the code formatting and linting:

```sh
bash ./scripts/quality.sh
```

(This command also runs the tests and coverage report.)

## Authentication

This project includes a complete JWT authentication system:

- **Login endpoint**: `POST /api/v1/auth/token`
- **Route protection**: Use `Depends(get_current_user)` to protect endpoints
- **Fake users**: For development, there is a fake users system

### Example usage:

```python
from fastapi import Depends
from app.core.auth import get_current_user
from app.core.auth.fake_users import FakeUser

@app.get("/protected")
def protected_route(current_user: FakeUser = Depends(get_current_user)):
    return {"message": f"Hello {current_user.full_name}!"}
```

### Default login:
- **Email**: `user@example.com`
- **Password**: `123456`

## Real Estate RAG

O catálogo de imóveis pode ser indexado em uma collection única no Qdrant.

Variáveis relevantes:

- `QDRANT_URL`
- `QDRANT_API_KEY`
- `QDRANT_COLLECTION_NAME`
- `QDRANT_EMBEDDING_MODEL`
- `QDRANT_VECTOR_SIZE`
- `QDRANT_SEARCH_LIMIT`
- `RAG_DENSE_WEIGHT`
- `RAG_BM25_WEIGHT`
- `RAG_CHUNK_SIZE`
- `RAG_CHUNK_OVERLAP`
- `RAG_MAX_CONTEXT_CHUNKS`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`

Quando um imóvel é criado ou atualizado, o reindex é enfileirado automaticamente.

## Catálogo administrativo

Payload base do imóvel:

```json
{
  "name": "Residencial Aurora",
  "information": "Apartamentos de 2 e 3 quartos com lazer completo.",
  "photos_url": ["https://cdn.example.com/aurora/fachada.jpg"],
  "videos_url": ["https://cdn.example.com/aurora/tour.mp4"],
  "documents_url": ["https://cdn.example.com/aurora/book.pdf"],
  "source_url": "https://example.com/aurora",
  "extraction_version": "seed-v1"
}
```

Rotas protegidas:

- `POST /api/prefix/v1/admin/buildings`
- `PUT /api/prefix/v1/admin/buildings/{building_id}`
- `POST /api/prefix/v1/admin/buildings/{building_id}/reindex`
- `POST /api/prefix/v1/admin/buildings/reindex-all`
- `GET /api/prefix/v1/admin/buildings`
- `GET /api/prefix/v1/admin/buildings/{building_id}`
- `GET /api/prefix/v1/admin/rag/search?query=...&building_id=...`

## Seed e reindex

Popular a base com dataset embutido:

```sh
uv run python scripts/seed_buildings.py --upsert --index-now
```

Popular a base com JSON externo:

```sh
uv run python scripts/seed_buildings.py --input ./buildings.json --upsert --index-now
```

Reindexar o catálogo inteiro:

```sh
uv run python scripts/reindex_buildings.py
```

## Validar o RAG

1. Faça login em `POST /api/prefix/auth/token`.
2. Crie ou atualize um imóvel pelas rotas admin.
3. Chame `GET /api/prefix/v1/admin/rag/search?query=lazer`.
4. Confirme que os `matches` e o `context` retornam os trechos esperados.

## Tools de mídia

As tools `get_all_building`, `get_building_info`, `search_building_information`, `send_photo_file`, `send_video_file` e `send_building_document` usam o catálogo persistido no banco. Para testar envio de fotos, vídeos e documentos, cadastre URLs válidas no imóvel e então provoque o fluxo conversacional para que a tool correspondente seja chamada.

## Guardrails

O pipeline agora aplica guardrails determinísticos em três pontos:

- inspeção de prompt injection na entrada;
- validação centralizada de tool calls antes da execução;
- sanitização de saída antes de persistir e responder.

Eventos internos esperados: `prompt_injection_suspected`, `tool_call_rejected`, `agent_output_sanitized` e `agent_structured_output_invalid`.
