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
