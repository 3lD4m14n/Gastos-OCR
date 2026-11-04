# Gestor de gastos con OCR de tickets

App web (PWA) para registrar gastos por categoría. Función principal: sacar 1 a 6 fotos de un
ticket de supermercado, extraer los ítems con un modelo de visión en AWS Bedrock, deduplicar las
líneas que aparecen en dos fotos y guardar los ítems categorizados. Sincroniza celular y PC.

La especificación completa está en `docs/spec.md`. Leela antes de diseñar cualquier módulo y
mantenela actualizada si una decisión cambia.

## Stack (decidido, no cambiar sin preguntar)

- Frontend: React 19 + Vite + TypeScript, PWA (`vite-plugin-pwa`), Tailwind + shadcn/ui,
  TanStack Query, Recharts. Auth con `react-oidc-context` + `oidc-client-ts`.
- Backend: FastAPI + Pydantic v2, SQLAlchemy 2 + Alembic, PostgreSQL 16.
- Auth: Amazon Cognito (managed login, Google como proveedor federado). La API solo valida el JWT
  contra el JWKS del user pool (`PyJWT`). No hay contraseñas ni endpoints de login propios.
- Imágenes: S3 privado con URLs prefirmadas (RustFS en local).
- OCR: Bedrock Converse API, `BEDROCK_MODEL_ID` por variable de entorno (Claude Haiku 4.5 por
  defecto, reintento con Sonnet si la suma no cuadra).
- Deploy: Lambda (imagen Docker + Lambda Web Adapter), RDS, Amplify Hosting, infra con AWS CDK
  en Python. Región `us-east-2`.

## Estructura del monorepo

```
/web      React + Vite (PWA)
/api      FastAPI (app/, tests/, alembic/)
/infra    AWS CDK
/docs     spec.md, fixtures de tickets, prototipos
docker-compose.yml   api + postgres + rustfs
```

## Reglas del dominio

- Moneda por defecto: guaraníes (PYG). Montos en `BIGINT`, nunca `float` ni decimales.
  Se muestran como `189.400 Gs` (`Intl.NumberFormat('es-PY')`).
- Zona horaria por defecto: `America/Asuncion`.
- El gasto se guarda por ítem; la categoría es por ítem.
- Alias de productos: viven en la tabla `products` (llave: últimos 8 dígitos del código de barras,
  respaldo: nombre normalizado). El nombre visible es `alias` si existe, si no `raw_name`.
- Todas las consultas filtran por `user_id` (el `sub` de Cognito).

## OCR y merge de fotos

- El modelo solo transcribe cada foto por separado; ordenar y deduplicar lo hace código
  determinista (`api/app/ocr/merge.py`). Ver la sección "Pipeline de OCR" de `docs/spec.md`.
- Dos ítems son el mismo en el borde entre fotos si coinciden `line_total` y código de barras
  (o nombre con `rapidfuzz` ≥ 85 si no hay código). Solo se compara el borde: los duplicados
  reales en medio del ticket se conservan.
- Fixtures: `docs/fixtures/receipts/<caso>/` con las fotos y un `gt.json` (formato: `images[]`
  con transcripción por foto, `items[]`, `detected_total`). Las fotos pueden estar en cualquier
  orden; eso es parte de la prueba.
- `docs/prototypes/merge_test.py` es el prototipo que ya pasa contra el fixture de El Ahorrazo
  (23 ítems, 189.400 Gs, en ambos órdenes). Portarlo a `api/app/ocr/merge.py` con tests en pytest.

## Cómo trabajar

- Seguir el roadmap por fases de `docs/spec.md` (Fase 0 → 3). Una fase por vez, terminando con
  algo que funcione de punta a punta.
- Tests: `pytest` en `/api`, `vitest` en `/web`. Todo cambio en el merge debe pasar los fixtures.
- Lint: `ruff` + `mypy` en Python, `eslint` + `tsc --noEmit` en TS.
- Nunca commitear credenciales de AWS ni de Cognito; usar `.env` (en `.gitignore`) y
  `.env.example` con los nombres de las variables.
- Textos de la UI en español.
