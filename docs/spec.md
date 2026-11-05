# Gestor de gastos con OCR de tickets — Especificación MVP

4 de noviembre de 2026 · Damian. Versión exportada del documento de especificación.

## Visión y alcance

Una app web responsive (instalable en el celular como PWA) para registrar gastos por categoría, con una función estrella: sacar una o varias fotos a un ticket, extraer los ítems con un modelo de visión en AWS Bedrock y guardarlos ya categorizados. La misma cuenta se usa en el celular y en la computadora; el servidor es la única fuente de verdad.

**Entra en el MVP**

- Inicio de sesión con Google o con email y contraseña, vía Amazon Cognito.
- Moneda por defecto: guaraníes (PYG), sin decimales.
- Categorías por defecto (Supermercado, Limpieza, Higiene, Bebidas, Almacén, Carnes, Verdulería, Farmacia, Hogar, Otros) y categorías propias; la categoría se asigna por ítem.
- Alta, edición y borrado manual de gastos.
- Escaneo de ticket con 1 a 6 fotos en cualquier orden, extracción de ítems, deduplicación de solapamientos y pantalla de revisión antes de guardar.
- Alias de productos: "PLUSBELLE SHA" se muestra como "Shampoo Plusbelle" en todos los tickets futuros.
- Dashboard: total del período, gasto por categoría, evolución mensual y últimos gastos.
- Despliegue en AWS usando los créditos.

**Queda fuera del MVP**

- App nativa (iOS/Android): la PWA alcanza para cámara y sincronización.
- Modo offline, presupuestos, gastos recurrentes, cuentas compartidas, multi-moneda, exportar a CSV.

## Stack

React + Vite como PWA, FastAPI en Python, PostgreSQL, imágenes en S3 y Claude Haiku en Bedrock para el OCR, todo desplegado en AWS para aprovechar los créditos.

| Capa | Elección | Por qué |
| --- | --- | --- |
| Frontend | React 19 + Vite + TypeScript, PWA con `vite-plugin-pwa` | Instalable en el celular, acceso a cámara sin app nativa |
| UI | Tailwind CSS + shadcn/ui | Componentes listos, mobile-first |
| Estado servidor | TanStack Query | Caché y re-sincronización entre dispositivos |
| Gráficos | Recharts | Torta/barras/líneas para el dashboard |
| Backend | FastAPI + Pydantic v2 + Uvicorn | Async, tipado, OpenAPI automático |
| ORM y migraciones | SQLAlchemy 2 + Alembic | Estándar en el ecosistema FastAPI |
| Base de datos | Amazon RDS PostgreSQL 16 | Relacional, `JSONB` para la salida cruda del OCR |
| Auth | Amazon Cognito (managed login + Google como proveedor) | Login con Google y con email en el mismo user pool; usuarios de prueba creados desde la consola o con `admin-create-user` |
| Auth en el front | `react-oidc-context` + `oidc-client-ts` | Authorization Code + PKCE contra Cognito, refresh automático |
| Auth en el back | `PyJWT` validando contra el JWKS del user pool | Sin contraseñas ni sesiones propias; el `sub` de Cognito es el ID de usuario |
| Imágenes | Amazon S3 privado + URLs prefirmadas | El celular sube directo a S3, el backend no recibe megas |
| OCR / extracción | Bedrock Converse API con Claude Haiku 4.5 (fallback Sonnet) | Lee tickets arrugados y devuelve JSON por *tool use* |
| Infra local | Docker Compose (api + postgres + rustfs) | Cognito se usa el pool `dev`, con `http://localhost:5173` como callback |
| CI/CD | GitHub Actions | Tests + build + deploy en cada push a `main` |

**Modelo.** En Bedrock, Claude Haiku 4.5 cuesta USD 1 por millón de tokens de entrada y USD 5 de salida; Amazon Nova Lite cuesta USD 0,06 / 0,24 pero es más flojo con fotos difíciles. El ID de modelo va en `BEDROCK_MODEL_ID` para poder comparar sin tocar código.

**Créditos.** Los créditos promocionales de AWS normalmente cubren los modelos de Anthropic en Bedrock, aunque hubo casos de modelos facturados vía Marketplace que no se descontaron. Hacer 10 escaneos de prueba y revisar *Billing → Credits* antes de seguir.

## Arquitectura

```
                 Amplify Hosting (sirve la PWA)
                          │
   ┌──────────── Clientes: Celular (PWA) · PC (navegador) ───────────┐
   │ PUT fotos (URL prefirmada)          │ API REST (Bearer Cognito)  │ login
   ▼                                     ▼                            ▼
 S3 fotos (privado)               API · Lambda (FastAPI) ──────► Cognito (Google / email)
   ▲                                     │ invoca async      └──► RDS PostgreSQL
   │                                     ▼                            ▲
   └──────────────────────── Worker OCR · Lambda ─────────────────────┘
                                         │
                                         ▼
                               Bedrock · Claude Haiku
```

- El celular sube las fotos directo a S3; el backend nunca recibe megas.
- El OCR corre en un worker separado para que la API responda al instante.
- La base de datos es la única fuente de verdad para los dos dispositivos.

El login lo resuelve Cognito: la PWA redirige a su pantalla de "Continuar con Google", recibe el token y lo manda en cada request; la API valida la firma con las claves públicas del user pool y crea la fila en `users` la primera vez que ve un `sub`. El worker lee las fotos de S3, llama a Bedrock, ordena, une y valida los ítems y guarda el resultado en Postgres; el cliente consulta el estado del ticket hasta que pasa a `needs_review`. En local, el worker es una `BackgroundTask` de FastAPI y S3 es RustFS (compatible con S3; reemplaza a MinIO, cuya imagen oficial dejó de estar disponible).

## Pipeline de OCR con fotos solapadas

El modelo transcribe cada foto por separado en una sola llamada, y el backend ordena y une las fotos con un algoritmo determinista que elimina solo las líneas repetidas en el borde entre foto y foto.

1. Fotos (1 a 6, en cualquier orden), comprimidas y subidas a S3.
2. Bedrock: una sola llamada con todas las fotos + esquema JSON.
3. Transcripción por foto: cada ítem con su monto, en orden dentro de la foto.
4. Ordenar fotos y unir bordes: mismo código y subtotal en el borde = 1 ítem.
5. ¿Suma = total? Si no, reintento una sola vez con Claude Sonnet (vuelve al paso 2); si sigue sin cuadrar, aviso.
6. Categorizar ítems con alias y categoría de productos conocidos.
7. Revisión del usuario: corrige, recategoriza y confirma.

**La llamada a Bedrock.** Una única request a la Converse API con todas las fotos (Claude acepta hasta 20 imágenes por request, de hasta 3,75 MB y 8.000 px cada una), `temperature = 0` y una herramienta `registrar_ticket` cuyo esquema obliga a devolver JSON. El prompt indica:

- Las fotos son tramos de un mismo ticket, pueden llegar en cualquier orden y pueden repetir líneas en los bordes.
- Transcribir cada foto por separado, sin deduplicar ni reordenar: eso lo hace el código.
- Cada ítem ocupa dos renglones: `cantidad x precio unitario Gs` arriba y `código  DESCRIPCIÓN  subtotalG  IVA` abajo. Devolver un objeto por ítem con los dos renglones combinados.
- Guaraníes: el punto es separador de miles y no hay decimales (`189.400` = 189400). La coma solo aparece en cantidades pesables (`0,456 x 18.900 Gs`).
- Marcar `cut_at_edge: true` si el renglón está cortado por el borde de la foto, e `is_uncertain: true` si algún número o letra no se lee con seguridad.
- Indicar si la foto contiene la cabecera (razón social, Timbrado) y si contiene `TOTAL GS`.
- Sugerir una categoría de la lista del usuario, que va en el prompt.

```python
class Item(BaseModel):            # mismos nombres que gt.json
    barcode: str | None           # "784076300762"; puede venir con dígitos cortados
    raw_name: str                 # "POLIFOAM FIBR", tal cual se lee
    quantity: Decimal = 1         # 2, o 0.456 en pesables
    unit_price: int | None        # guaraníes
    line_total: int               # guaraníes; negativo si es descuento
    iva_rate: Literal[5, 10, 0] | None
    kind: Literal["item", "discount"] = "item"
    cut_at_edge: bool = False
    is_uncertain: bool = False
    category_hint: str | None = None

class ImageRead(BaseModel):
    photo_position: int           # orden en que el usuario sacó/subió la foto
    has_header: bool
    items: list[Item]
    detected_total: int | None    # solo si la foto muestra TOTAL GS

class TicketOCR(BaseModel):
    merchant: str | None
    ruc: str | None
    purchased_at: datetime | None
    images: list[ImageRead]
```

**El merge.** Primero se ordenan las fotos: la que tiene cabecera va primera, la que tiene `TOTAL GS` va última, y entre las demás gana el orden que maximiza las líneas solapadas (con 6 fotos son 720 permutaciones, instantáneo). Después, para cada par de fotos consecutivas se busca el bloque más largo de ítems donde el final de una coincide con el principio de la siguiente. Dos ítems "coinciden" si tienen el mismo `line_total` y el mismo código de barras (últimos 8 dígitos, porque el borde de la foto suele comerse los primeros); si falta el código, se compara el nombre normalizado con `rapidfuzz` (≥ 85 %). Las líneas `cut_at_edge` se descartan antes de ordenar y de unir: si no, una línea cortada anula el solapamiento y las fotos pueden quedar mal ordenadas.

```python
def same(x: Item, y: Item) -> bool:
    if x.line_total != y.line_total:
        return False
    if x.barcode and y.barcode:
        return x.barcode[-8:] == y.barcode[-8:]
    return fuzz.ratio(norm(x.raw_name), norm(y.raw_name)) >= 85

def overlap(a: list[Item], b: list[Item], max_k: int = 12) -> int:
    for k in range(min(len(a), len(b), max_k), 0, -1):
        if all(same(x, y) for x, y in zip(a[-k:], b[:k])):
            return k
    return 0

def complete(img: ImageRead) -> list[Item]:
    return [i for i in img.items if not i.cut_at_edge]

def order_images(imgs: list[ImageRead]) -> list[ImageRead]:
    def score(p):  # usa solo líneas completas, igual que merge()
        s = sum(overlap(complete(p[i]), complete(p[i + 1])) for i in range(len(p) - 1))
        return s + 100 * p[0].has_header + 100 * (p[-1].detected_total is not None)
    return list(max(permutations(imgs), key=score))

def merge(imgs: list[ImageRead]) -> list[Item]:
    ordered = order_images(imgs)
    merged = complete(ordered[0])
    for img in ordered[1:]:
        items = complete(img)
        merged.extend(items[overlap(merged, items):])
    return merged
```

**Duplicados reales vs. solapamiento.** Como solo se compara el borde entre fotos, dos compras iguales en medio del ticket nunca se fusionan. El caso ambiguo es una sola línea repetida justo en el borde (`k = 1`): se prueban las dos variantes, con y sin fusionar, y gana la que hace cuadrar la suma con el total; si ninguna cuadra o no se detectó el total, se conservan las dos copias y la segunda llega a revisión marcada como posible duplicado, porque borrar un ítem de más es más fácil que notar uno que falta. Si entre dos fotos no hay ninguna línea en común, se avisa "puede faltar un tramo entre la foto 2 y la 3".

**Validación.** Se suman los `line_total` y se comparan con `detected_total`; en guaraníes no hay redondeos, así que la tolerancia es 0. El resultado se guarda en `ocr_raw` y los ítems pasan a la memoria de productos: si el código o el nombre ya existe en `products`, se usan su alias y su categoría; si no, la sugerencia del modelo, y si no, "Otros".

**Prueba con el ticket de El Ahorrazo (25/09/26)** — `docs/fixtures/receipts/ahorrazo-2026-09-25/`:

| Caso | Orden elegido | Líneas solapadas | Ítems | Suma | Resultado |
| --- | --- | --- | --- | --- | --- |
| Fotos en orden | 1 → 2 | 4 | 23 de 23 | 189.400 Gs | Igual a `gt.json` |
| Fotos invertidas | 1 → 2 | 4 | 23 de 23 | 189.400 Gs | Igual a `gt.json` |
| Sin deduplicar | — | — | 27 | 211.200 Gs | Sobran 21.800 Gs |

El bloque solapado (OMO, jabón Plusbelle y dos Polifoam) contiene a su vez un duplicado real, y fuera del borde hay compras repetidas legítimas (2 Rexona, 2 arroz Mariela, 3 atún Norte) que el algoritmo no toca. Falta medir la otra mitad: que Haiku produzca esas transcripciones a partir de las fotos.

## Requisitos funcionales

| ID | Historia | Criterio de aceptación |
| --- | --- | --- |
| HU-01 | Inicio sesión con Google o con email | Botón "Continuar con Google" en la pantalla de Cognito; usuarios de prueba con email y contraseña; la sesión se renueva sola durante 30 días desde el inicio de sesión; después hay que volver a entrar (la rotación del refresh token no extiende ese plazo) |
| HU-02 | Veo mis gastos en el celular y en la PC | Un gasto creado en un dispositivo aparece en el otro al recargar o a los 30 s |
| HU-03 | Gestiono categorías | 10 categorías por defecto; crear, renombrar, cambiar color y borrar (sus gastos pasan a "Otros") |
| HU-04 | Cargo un gasto a mano | Fecha, monto en guaraníes, descripción, categoría; queda en el dashboard al instante |
| HU-05 | Saco 1 a 6 fotos de un ticket | Miniaturas, puedo borrar y repetir una foto antes de enviar; el orden no importa |
| HU-06 | La app extrae los ítems | En menos de 30 s veo comercio, fecha, total y la lista de ítems con categoría sugerida |
| HU-07 | Los ítems repetidos por solapamiento no se duplican | Un ítem que aparece en dos fotos se cuenta una vez; dos compras iguales reales se cuentan dos veces |
| HU-08 | Reviso antes de guardar | Edito nombre, monto y categoría de cada ítem, borro o agrego ítems; veo si la suma coincide con el total |
| HU-09 | Confirmo el ticket | Se guardan los ítems como gastos ligados al ticket; puedo volver a ver las fotos |
| HU-10 | Veo el dashboard | Total del mes, gasto por categoría, evolución de los últimos 6 meses, filtro por rango de fechas |
| HU-11 | La app recuerda mis categorías | Si cambié "LIMCROM LAVAN" a Limpieza, el próximo ticket la sugiere en Limpieza |
| HU-12 | Le pongo alias a un producto | Escribo "Shampoo Plusbelle" para "PLUSBELLE SHA"; todos los gastos pasados y futuros muestran el alias, y el nombre original sigue visible en el detalle |

**Requisitos no funcionales**

- Montos en guaraníes enteros; se muestran como `189.400 Gs`.
- Fotos comprimidas en el navegador a ≤ 1600 px de lado mayor y ≤ 1 MB antes de subir.
- Todas las consultas filtradas por `user_id`; nadie ve datos de otro usuario.
- Límite de 30 escaneos por usuario por día.
- Fechas y "mes actual" calculados en `America/Asuncion`.

## Modelo de datos

| Tabla | Campos principales | Notas |
| --- | --- | --- |
| `users` | `id` = `sub` de Cognito, `email`, `name`, `currency` (default `PYG`), `timezone` (default `America/Asuncion`), `created_at` | Se crea en la primera request autenticada |
| `categories` | `id`, `user_id`, `name`, `color`, `icon`, `is_default` | Único por (`user_id`, `name`); se crean 10 al crear el usuario |
| `products` | `id`, `user_id`, `barcode` nullable, `raw_name`, `name_key`, `alias` nullable, `category_id`, `last_unit_price`, `times_bought` | Alias y memoria de categoría. Únicos por (`user_id`, `barcode`) y (`user_id`, `name_key`) |
| `receipts` | `id`, `user_id`, `merchant`, `ruc`, `purchased_at`, `total_declared` BIGINT, `status`, `model_id`, `ocr_raw` JSONB, `error`, `created_at` | `uploading` → `processing` → `needs_review` → `confirmed` (o `failed`) |
| `receipt_images` | `id`, `receipt_id`, `s3_key`, `upload_position`, `merged_position`, `width`, `height` | `merged_position` es el orden elegido por el merge |
| `expenses` | `id`, `user_id`, `receipt_id` nullable, `product_id` nullable, `category_id`, `description`, `quantity` NUMERIC(10,3), `unit_price` BIGINT, `amount` BIGINT, `iva_rate`, `spent_at` DATE, `notes`, `created_at` | Índice en (`user_id`, `spent_at`) |

**Alias.** Al confirmar un ticket, cada ítem se busca en `products` por código de barras (últimos 8 dígitos) y después por `name_key`; si no existe, se crea. El nombre visible es `products.alias` si existe, si no `raw_name`. Renombrar un producto cambia todos sus gastos pasados.

Montos en `BIGINT` de guaraníes, nunca `float`. `ocr_raw` guarda la respuesta completa del modelo para depurar y re-procesar sin volver a pagar.

## API REST

Todo bajo `/api/v1`, con `Authorization: Bearer <token de Cognito>`. Sin endpoints de login.

| Método | Ruta | Qué hace |
| --- | --- | --- |
| GET | `/users/me` | Perfil; la primera vez crea el usuario y sus 10 categorías |
| PATCH | `/users/me` | Cambiar moneda o zona horaria |
| GET · POST | `/categories` | Listar y crear |
| PATCH · DELETE | `/categories/{id}` | Editar; al borrar, los gastos pasan a "Otros" |
| GET | `/expenses?from=&to=&category_id=&q=&page=` | Lista paginada; `q` busca en alias y nombre original |
| POST | `/expenses` | Gasto manual |
| PATCH · DELETE | `/expenses/{id}` | Editar o borrar |
| GET | `/products?q=&category_id=` | Productos con alias, categoría, último precio y veces comprado |
| PATCH | `/products/{id}` | Alias y categoría por defecto |
| POST | `/receipts` | Body `{image_count}`; devuelve una URL prefirmada de S3 por foto |
| POST | `/receipts/{id}/process` | Lanza el OCR; responde `202` |
| GET | `/receipts/{id}` | Estado + ítems con alias, categoría sugerida y advertencias |
| POST | `/receipts/{id}/confirm` | Ítems finales (y alias nuevos); crea `expenses` y actualiza `products` |
| GET | `/receipts/{id}/images` | URLs prefirmadas de lectura |
| DELETE | `/receipts/{id}` | Borra ticket, fotos y gastos asociados |
| GET | `/stats/summary?from=&to=` | Total, por categoría, por mes, top comercios y productos |

**Flujo de escaneo:** `POST /receipts` → `PUT` de cada foto a S3 → `POST /receipts/{id}/process` → `GET /receipts/{id}` cada 2 s hasta `needs_review` → revisión → `POST /receipts/{id}/confirm`.

```json
{
  "id": "b6f…",
  "status": "needs_review",
  "merchant": "Supermercado El Ahorrazo",
  "ruc": "80096143-9",
  "purchased_at": "2026-09-25T21:37:00-03:00",
  "total_declared": 189400,
  "items_sum": 189400,
  "image_order": [2, 1],
  "items": [
    {"barcode": "779074000025", "raw_name": "PLUSBELLE SHA",
     "display_name": "Shampoo Plusbelle", "product_id": "…",
     "quantity": 1, "unit_price": 11000, "line_total": 11000,
     "iva_rate": 10, "category_id": "…", "category_source": "product",
     "is_uncertain": false, "flags": []}
  ],
  "warnings": []
}
```

## Frontend

| Pantalla | Contenido |
| --- | --- |
| Login | Redirige al login de Cognito ("Continuar con Google" o email) |
| Dashboard | Total del período en Gs, torta por categoría, barras de 6 meses, últimos 10 gastos, selector de rango |
| Escanear | "Sacar foto", tira de miniaturas, guía "solapá un poco cada foto con la anterior", "Procesar" |
| Revisión del ticket | Cabecera, ítems editables con alias y categoría; aviso si la suma no cuadra; "posible duplicado" e `is_uncertain` resaltados |
| Gastos | Filtros por fecha, categoría y texto; alta manual; detalle con fotos y nombre original |
| Productos | Nombre original, alias editable, categoría por defecto, último precio, veces comprado |
| Categorías | Color e ícono, crear y editar |

- Cámara: `<input type="file" accept="image/*" capture="environment">`, una vez por foto. Requiere HTTPS (en local: `vite --host` + `mkcert` o túnel `cloudflared`).
- Antes de subir: `browser-image-compression`, lado mayor ≤ 1600 px, JPEG 0,85, sin EXIF.
- Sincronización: TanStack Query re-pide al volver el foco y cada 30 s en el dashboard.
- Montos: `Intl.NumberFormat('es-PY', { maximumFractionDigits: 0 })` + `Gs`; inputs solo enteros.

## Despliegue, costos y seguridad

| Pieza | Servicio | Detalle |
| --- | --- | --- |
| Frontend | AWS Amplify Hosting | HTTPS y dominio propio |
| Auth | Cognito: pools `dev` y `prod` | Google federado; callbacks `http://localhost:5173` (dev) y dominio (prod) |
| API | Lambda (imagen Docker + Lambda Web Adapter), Function URL | FastAPI sin cambios |
| Worker OCR | Misma imagen, otro handler, invocación asíncrona | Timeout 120 s, 1 GB |
| Base de datos | RDS PostgreSQL `db.t4g.micro`, 20 GB | Backups de 7 días |
| Imágenes | S3 privado, Glacier a los 90 días | CORS solo para tu dominio |
| Secretos | SSM Parameter Store; Secrets Manager para el secreto de Google | `DATABASE_URL`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `BEDROCK_MODEL_ID`; `gastos-ocr/dev/google-client-secret`, que CDK referencia sin copiarlo al código |
| IaC | AWS CDK en Python | Un `cdk deploy` levanta todo |

**Costo (aproximado).** Un ticket de 3 fotos ≈ 9.000 tokens de entrada y 1.500 de salida ≈ USD 0,016 con Haiku 4.5. 100 tickets/mes ≈ USD 1,60 de Bedrock; RDS ≈ USD 13/mes; el resto, centavos.

**Seguridad**

- Cada consulta filtra por el `user_id` del token; tests que intentan leer recursos de otro usuario.
- La API valida firma, `iss`, `client_id`, `token_use` y expiración del token de Cognito.
- S3 sin acceso público; URLs de subida de 5 min, solo `image/jpeg`, máx. 2 MB.
- Rol IAM de la Lambda con `bedrock:InvokeModel` solo sobre el modelo elegido.
- 30 escaneos por usuario por día (`slowapi`).
- AWS Budgets con alarma en USD 20.

## Roadmap

1. **Fase 0 · Base.** Monorepo (`/web`, `/api`, `/infra`), Docker Compose con Postgres y RustFS, FastAPI con health check, Vite + PWA vacía, CI con tests y lint. User pool `dev` con Google y un usuario de prueba.
2. **Fase 1 · Gastos sin OCR.** Login con Cognito, categorías, gastos manuales, dashboard en guaraníes. Deploy a AWS al final.
3. **Fase 2 · Escaneo.** Captura múltiple, S3, worker OCR con Bedrock, orden y merge, validación, revisión, confirmación, `products` con alias. Set de regresión: el fixture de El Ahorrazo + ~20 tickets reales.
4. **Fase 3 · Pulido.** Pantalla Productos, rate limits, alarmas de costo, errores del OCR, íconos de la PWA.

**Después del MVP:** CSV, presupuestos, gastos recurrentes, cola SQS para el OCR, offline, multi-moneda.

## Decisiones tomadas

| Tema | Decisión |
| --- | --- |
| Backend | FastAPI |
| Autenticación | Cognito con Google; usuarios de prueba con email y contraseña en el pool `dev` |
| Base de datos | Amazon RDS PostgreSQL |
| Moneda | Guaraníes (PYG), sin decimales |
| Categorías | Por ítem |
| Nombres de productos | Alias por producto, código de barras como llave |
| Modelo de OCR | Claude Haiku 4.5; falta compararlo con Nova Lite y Sonnet sobre las fotos del fixture |

## Fuentes

- [AWS Bedrock pricing 2026 — Bacancy](https://www.bacancytechnology.com/blog/aws-bedrock-pricing)
- [Anthropic Claude Messages API — Amazon Bedrock User Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages.html)
- [Créditos promocionales y modelos de Anthropic — AWS re:Post](https://repost.aws/questions/QUrl2nATrQRWi1g2CV5ra5eA/claude-opus-4-5-is-being-billed-under-aws-marketplace)
