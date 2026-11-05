# Gestor de gastos con OCR de tickets

PWA para registrar gastos en guaraníes y cargar tickets de supermercado con fotos.

| Carpeta | Contenido |
| --- | --- |
| `api/` | FastAPI y el merge de OCR (`app/ocr/merge.py`) |
| `web/` | React + Vite (PWA) |
| `infra/` | AWS CDK: `InfraStack` (Cognito de desarrollo) y `GastosProd` (producción) |

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

Para iniciar sesión hacen falta los identificadores del pool de Cognito de desarrollo, que salen
de las salidas de `InfraStack`:

- En `.env`: `COGNITO_USER_POOL_ID` y `COGNITO_CLIENT_ID`. Sin ellos, la API responde 503 en las
  rutas autenticadas.
- En `web/.env.local`: las variables de `web/.env.example`.

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

## Deploy

En AWS la base es Aurora DSQL, sin VPC; en local y en CI, Postgres 16. El deploy es manual, en
`us-east-2`, y necesita Docker y credenciales de AWS.

```sh
cd infra
npx aws-cdk@2.1147.0 diff GastosProd
npx aws-cdk@2.1147.0 deploy GastosProd \
  --parameters BudgetEmail=<email-para-alertas> \
  --parameters AllowedEmails=<email-1>,<email-2>
./scripts/deploy_web.sh
```

Las migraciones corren dentro de `cdk deploy`: si fallan, la API no se actualiza. Los emails se
pasan como parámetros para no versionarlos. Solo pueden crear cuenta los de `AllowedEmails`; la
restricción se aplica al crear la cuenta, así que quitar un email no desactiva una cuenta existente.

Agregá la salida `GoogleRedirectUri` a las URI de redirección autorizadas del cliente OAuth de
Google. El secreto de Google vive en Secrets Manager y nunca en el repositorio.

La base, el bucket y el pool de producción se conservan aunque se borre el stack.
