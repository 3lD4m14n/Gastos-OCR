# Gestor de gastos con OCR de tickets

PWA para registrar gastos en guaraníes y cargar tickets de supermercado con fotos.
La especificación está en [`docs/spec.md`](docs/spec.md).

| Carpeta | Contenido |
| --- | --- |
| `api/` | FastAPI y el merge de OCR (`app/ocr/merge.py`) |
| `web/` | React + Vite (PWA) |
| `infra/` | AWS CDK; por ahora, un stack vacío |
| `docs/` | Especificación, fixtures y prototipos |

Requisitos: Docker, [uv](https://docs.astral.sh/uv/) y Node 26. Para `cdk`, Node 24 evita el aviso
de versión no probada.

## Levantar en local

```sh
docker compose up -d --build --wait   # API, Postgres y RustFS (S3 local)
curl http://127.0.0.1:8000/health/ready

cd web && npm ci && npm run dev       # http://localhost:5173
```

- API: <http://127.0.0.1:8000/docs>
- Consola de RustFS: <http://127.0.0.1:9001>

Los valores por defecto están en `.env.example`. Son solo para desarrollo local. Para cambiarlos,
copiá el archivo a `.env`.

`docker compose down` detiene todo; con `--volumes` también borra los datos locales.

## Tests y lint

```sh
cd api && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
cd web && npm run lint && npm run typecheck && npm test && npm run build
cd infra && uv run ruff check . && uv run mypy && uv run pytest && npx aws-cdk@2.1147.0 synth --strict --quiet
```

Prueba del flujo de subida contra RustFS, con el stack levantado:

```sh
cp .env.example api/.env
cd api && uv run python -m scripts.smoke_s3
```

## Fixtures

Antes de agregar un ticket real, seguí [`docs/fixtures/README.md`](docs/fixtures/README.md) para no
publicar datos personales.
