#!/usr/bin/env bash

set -e

echo "🎨 Formatando código com Ruff..."
uv run ruff check app scripts --fix
uv run ruff format app

echo ""
echo "🔍 Verificando tipagem com MyPy..."
uv run mypy app/

echo ""
echo "🧪 Executando testes com cobertura..."
bash ./scripts/test.sh

echo ""
echo "✅ Todas as verificações de qualidade foram concluídas com sucesso!"
